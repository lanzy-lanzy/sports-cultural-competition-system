from django import forms
from django.contrib.auth.models import User
from django.db.models import Q

from accounts.models import UserProfile
from eligibility.models import EligibilityRecord
from participants.models import Participant
from sports.models import SportsEvent
from .models import Department, Team, TeamMembership, TeamStaff
from .services import assignable_team_events, assignment_players


INPUT_CLASS = (
    'h-12 w-full rounded-xl border border-slate-200 bg-slate-50/70 px-4 '
    'text-sm text-slate-800 outline-none transition focus:border-campus '
    'focus:bg-white focus:ring-4 focus:ring-teal-100'
)


class TeamRosterFilterForm(forms.Form):
    q = forms.CharField(
        required=False, max_length=200, label='Search players',
        widget=forms.TextInput(attrs={'placeholder': 'Name, participant ID, or jersey number'}),
    )
    status = forms.ChoiceField(
        required=False, label='Membership status',
        choices=[('', 'All membership statuses'), *TeamMembership.Status.choices],
    )
    category = forms.ChoiceField(
        required=False, choices=[('', 'All categories'), *Participant.Category.choices],
    )
    gender = forms.ChoiceField(
        required=False,
        choices=[('', 'All genders'), *Participant._meta.get_field('gender').choices],
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs['class'] = INPUT_CLASS


class DepartmentForm(forms.ModelForm):
    class Meta:
        model = Department
        fields = ('code', 'name')
        widgets = {
            'code': forms.TextInput(attrs={'placeholder': 'e.g. SBA, CAS, CON, SHM', 'class': INPUT_CLASS}),
            'name': forms.TextInput(attrs={'placeholder': 'Optional full department name', 'class': INPUT_CLASS}),
        }

    def clean_code(self):
        code = (self.cleaned_data.get('code') or '').strip().upper()
        if not code:
            raise forms.ValidationError('Enter a department code.')
        qs = Department.objects.filter(code__iexact=code)
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError(f'Department "{code}" already exists.')
        return code


class TeamForm(forms.ModelForm):
    department = forms.ChoiceField(required=False, label='Department')

    class Meta:
        model = Team
        fields = ('department', 'name', 'category', 'description', 'logo', 'status', 'sports_categories')
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
            'sports_categories': forms.CheckboxSelectMultiple,
        }

    def __init__(self, *args, allow_status=True, force_approved=False, require_department=False, **kwargs):
        super().__init__(*args, **kwargs)
        self.force_approved = force_approved
        self.fields['department'].required = require_department

        approved_qs = Team.objects.filter(status=Team.Status.APPROVED).exclude(department='')
        if self.instance.pk:
            approved_qs = approved_qs.exclude(pk=self.instance.pk)
        approved_codes = {code.strip().upper() for code in approved_qs.values_list('department', flat=True)}
        self.locked_departments = sorted(approved_codes)

        active_depts = list(Department.objects.filter(is_active=True).order_by('code'))
        if active_depts:
            all_choices = [
                (dept.code, f'{dept.code} — {dept.name}' if dept.name else dept.code)
                for dept in active_depts
            ]
        else:
            all_choices = list(Team.Department.choices)

        current_code = (self.instance.department or '').strip().upper() if self.instance.pk else ''
        selectable = []
        for code, label in all_choices:
            if code in approved_codes and code != current_code:
                continue
            selectable.append((code, label))

        if current_code and not any(code == current_code for code, _ in selectable):
            selectable.insert(0, (current_code, current_code))

        self.fields['department'].choices = [('', 'Select department')] + selectable

        if self.instance.pk and self.instance.status == Team.Status.APPROVED and current_code:
            self.fields['department'].disabled = True

        if force_approved or not allow_status:
            self.fields.pop('status')
        for field in self.fields.values():
            field.widget.attrs['class'] = INPUT_CLASS
        sports = self.fields['sports_categories']
        available = Q(is_active=True)
        if self.instance.pk:
            available |= Q(teams=self.instance.pk)
        sports.queryset = sports.queryset.filter(available).distinct()
        sports.widget.attrs['class'] = 'team-sport-options'

    def clean_department(self):
        dept = (self.cleaned_data.get('department') or '').strip().upper()
        if not dept:
            return ''
        approved_qs = Team.objects.filter(status=Team.Status.APPROVED, department__iexact=dept)
        if self.instance.pk:
            approved_qs = approved_qs.exclude(pk=self.instance.pk)
        if approved_qs.exists():
            raise forms.ValidationError(
                f'{dept} already has an approved team and cannot be selected again.'
            )
        return dept

    def clean(self):
        cleaned = super().clean()
        category = cleaned.get('category')
        sports = cleaned.get('sports_categories')
        if sports is not None:
            if category == Team.Category.CULTURAL:
                cleaned['sports_categories'] = sports.none()
            elif self.instance._state.adding and category == Team.Category.SPORTS and not sports:
                self.add_error('sports_categories', 'Select at least one sport for a Sports Team.')
        return cleaned

    def save(self, commit=True):
        team = super().save(commit=False)
        if self.force_approved:
            team.status = Team.Status.APPROVED
        if commit:
            team.save()
            self.save_m2m()
        return team


class RosterPlayerCheckboxes(forms.CheckboxSelectMultiple):
    def __init__(self, unavailable):
        super().__init__()
        self.unavailable = unavailable

    def create_option(self, name, value, label, selected, index, subindex=None, attrs=None):
        option = super().create_option(name, value, label, selected, index, subindex, attrs)
        if str(value) in self.unavailable:
            option['attrs']['disabled'] = True
        return option


class TeamEventRosterForm(forms.Form):
    def __init__(self, *args, team, selected_sports_only=False, **kwargs):
        super().__init__(*args, **kwargs)
        events = assignable_team_events()
        if selected_sports_only:
            events = events.filter(sport_type__in=team.sports_categories.all())
        self.events = list(events.select_related(
            'competition', 'sport_type',
        ).order_by('competition__name', 'competition_id', 'sport_type__name', 'name', 'pk'))
        self.event_rosters = []
        if not self.events:
            return

        assigned = {}
        inactive_members = set()
        if team.pk:
            for member in team.memberships.prefetch_related('events'):
                if member.status != TeamMembership.Status.ACTIVE:
                    inactive_members.add(member.participant_id)
                for event in member.events.all():
                    assigned.setdefault(event.pk, []).append(member.participant_id)
        player_options = assignment_players(team)
        players = list(player_options)
        unapproved_eligibility = set(EligibilityRecord.objects.filter(
            competition_id__in={event.competition_id for event in self.events},
            participant_id__in=player_options.order_by().values('pk'),
        ).exclude(status=EligibilityRecord.Status.APPROVED).values_list('participant_id', 'competition_id'))
        for event in self.events:
            name = str(event.pk)
            initial = assigned.get(event.pk, [])
            current = set(initial)
            choices = []
            unavailable = set()
            for player in players:
                player_id = str(player.pk)
                label = f'{player.name} ({player.participant_id})'
                if player.pk not in current:
                    if player.status != 'ACTIVE' or (
                        event.gender in ('male', 'female') and player.gender != event.gender
                    ) or (event.category != 'OPEN' and player.category != event.category):
                        continue
                    if player.pk in inactive_members:
                        label += ' · Inactive roster member'
                        unavailable.add(player_id)
                    elif (player.pk, event.competition_id) in unapproved_eligibility:
                        label += ' · Eligibility approval required'
                        unavailable.add(player_id)
                choices.append((player_id, label))
            req_suffix = f' · Required: {event.players_per_event} player{"s" if event.players_per_event != 1 else ""}' if event.players_per_event else ''
            self.fields[name] = forms.MultipleChoiceField(
                choices=choices, initial=initial, required=False, widget=RosterPlayerCheckboxes(unavailable),
                label=f'{event.name} · {event.get_category_display()} · {event.get_gender_display()}{req_suffix}',
            )
            self.event_rosters.append((event, self[name]))

    def clean(self):
        cleaned = super().clean()
        submitted = set(self.data.getlist('roster-event'))
        if submitted - self.fields.keys():
            raise forms.ValidationError('An event is no longer available. Review the event selections.')
        events_by_key = {str(event.pk): event for event in self.events}
        result = {}
        for key, values in cleaned.items():
            if key not in submitted:
                continue
            event = events_by_key.get(key)
            if event and event.players_per_event and len(values) > event.players_per_event:
                self.add_error(
                    key,
                    f'Cannot assign more than {event.players_per_event} player(s) to {event.name}.',
                )
            result[key] = values
        return result

    def selections(self):
        return {int(key): {int(value) for value in values} for key, values in self.cleaned_data.items()}


class TeamStaffForm(forms.Form):
    user = forms.ModelChoiceField(queryset=User.objects.none())
    role = forms.ChoiceField(choices=TeamStaff.Role.choices)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['user'].queryset = User.objects.filter(
            account_profile__role=UserProfile.Role.TEAM_MANAGER,
            is_active=True,
        ).order_by('first_name', 'last_name', 'username')
        for field in self.fields.values():
            field.widget.attrs['class'] = INPUT_CLASS


class TeamMembershipForm(forms.ModelForm):
    participant = forms.ModelChoiceField(queryset=Participant.objects.none())
    events = forms.ModelMultipleChoiceField(queryset=SportsEvent.objects.none(), required=False, widget=forms.CheckboxSelectMultiple, label='Sports events')

    class Meta:
        model = TeamMembership
        fields = ('participant', 'member_number', 'events')

    def __init__(self, *args, team, **kwargs):
        super().__init__(*args, **kwargs)
        self.team = team
        from .services import available_member_events
        self.fields['events'].queryset = available_member_events(team)
        self.fields['events'].label_from_instance = lambda event: f'{event.competition.name} — {event.name}'
        self.fields['participant'].queryset = Participant.objects.filter(
            team_membership__isnull=True,
            status='ACTIVE',
        ).order_by('name')
        for field in self.fields.values():
            field.widget.attrs['class'] = INPUT_CLASS
        self.fields['events'].widget.attrs['class'] = 'team-event-options'

    def clean(self):
        cleaned = super().clean()
        if cleaned.get('participant') is not None and 'events' in cleaned:
            from .services import validate_member_events
            member = TeamMembership(team=self.team, participant=cleaned['participant'])
            try:
                validate_member_events(member, list(cleaned['events']))
            except forms.ValidationError as error:
                self.add_error('events', error)
        return cleaned

    def clean_member_number(self):
        member_number = self.cleaned_data.get('member_number')
        if member_number is not None and member_number > 999:
            raise forms.ValidationError('Member number must be between 1 and 999.')
        return member_number


class TeamMemberEventsForm(forms.Form):
    events = forms.ModelMultipleChoiceField(queryset=SportsEvent.objects.none(), required=False, widget=forms.CheckboxSelectMultiple)

    def __init__(self, *args, membership, **kwargs):
        super().__init__(*args, **kwargs)
        from sports.models import SportsEvent
        from .services import available_member_events
        self.membership = membership
        self.fields['events'].queryset = SportsEvent.objects.filter(
            Q(pk__in=available_member_events(membership.team, membership.participant).values('pk'))
            | Q(assigned_team_members=membership),
        ).distinct().select_related('competition').order_by('competition__name', 'name')
        self.fields['events'].initial = membership.events.all()
        self.fields['events'].label_from_instance = lambda event: f'{event.competition.name} — {event.name}'
        self.fields['events'].widget.attrs['class'] = 'team-event-options'

    def clean_events(self):
        from .services import validate_member_events
        events = self.cleaned_data['events']
        validate_member_events(self.membership, list(events))
        return events


class TeamPlayerRegistrationForm(forms.Form):
    """Allows an approved Team Manager to register a new player directly under their team."""

    first_name = forms.CharField(max_length=100, label='First name')
    middle_name = forms.CharField(max_length=100, required=False, label='Middle name (optional)')
    last_name = forms.CharField(max_length=100, label='Last name')
    phone = forms.CharField(max_length=20, label='Phone number')
    identification_number = forms.CharField(max_length=100, required=False, label='School ID number')
    age = forms.IntegerField(min_value=5, max_value=120, required=False, label='Age')
    gender = forms.ChoiceField(
        choices=Participant._meta.get_field('gender').choices,
        initial='prefer_not_to_say',
    )
    category = forms.ChoiceField(
        choices=Participant.Category.choices,
        initial=Participant.Category.OPEN,
    )
    member_number = forms.IntegerField(min_value=1, max_value=999, required=False, label='Jersey / roster number')
    events = forms.ModelMultipleChoiceField(
        queryset=SportsEvent.objects.none(),
        required=False,
        widget=forms.CheckboxSelectMultiple,
        label='Assign to sports / events (optional)',
    )

    def __init__(self, *args, team, **kwargs):
        super().__init__(*args, **kwargs)
        self.team = team
        from .services import available_member_events
        self.fields['events'].queryset = available_member_events(team)
        self.fields['events'].label_from_instance = lambda event: f'{event.competition.name} — {event.name}'
        for field in self.fields.values():
            field.widget.attrs['class'] = INPUT_CLASS
        self.fields['events'].widget.attrs['class'] = 'team-event-options'

    def clean_member_number(self):
        number = self.cleaned_data.get('member_number')
        if number is not None and TeamMembership.objects.filter(team=self.team, member_number=number).exists():
            raise forms.ValidationError('That jersey number is already used on this team.')
        return number

    def save(self, user):
        from django.db import transaction
        from .services import set_member_events

        parts = [
            self.cleaned_data['first_name'].strip(),
            self.cleaned_data.get('middle_name', '').strip(),
            self.cleaned_data['last_name'].strip(),
        ]
        full_name = ' '.join(p for p in parts if p)
        with transaction.atomic():
            participant = Participant.objects.create(
                name=full_name,
                phone=self.cleaned_data['phone'].strip(),
                identification_number=(self.cleaned_data.get('identification_number') or '').strip(),
                age=self.cleaned_data.get('age'),
                gender=self.cleaned_data['gender'],
                category=self.cleaned_data['category'],
                team_name=self.team.name,
                status='ACTIVE',
            )
            membership = TeamMembership.objects.create(
                team=self.team,
                participant=participant,
                member_number=self.cleaned_data.get('member_number'),
                status=TeamMembership.Status.ACTIVE,
            )
            events = list(self.cleaned_data.get('events') or [])
            if events:
                set_member_events(membership, events, user)
            return membership
