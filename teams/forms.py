from django import forms
from django.contrib.auth.models import User
from django.db.models import Q

from accounts.models import UserProfile
from participants.models import Participant
from sports.models import SportsEvent
from .models import Team, TeamMembership, TeamStaff
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


class TeamForm(forms.ModelForm):
    class Meta:
        model = Team
        fields = ('name', 'category', 'description', 'logo', 'status', 'sports_categories')
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
            'sports_categories': forms.CheckboxSelectMultiple,
        }

    def __init__(self, *args, allow_status=True, force_approved=False, **kwargs):
        super().__init__(*args, **kwargs)
        self.force_approved = force_approved
        # Competition management approves a team the moment it creates one, so
        # the status is fixed rather than offered as a choice. Team managers
        # still submit for approval, and editors keep the ability to suspend.
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
        if team.pk:
            for member in team.memberships.prefetch_related('events'):
                for event in member.events.all():
                    assigned.setdefault(event.pk, []).append(member.participant_id)
        players = list(assignment_players(team))
        for event in self.events:
            name = str(event.pk)
            initial = assigned.get(event.pk, [])
            current = set(initial)
            choices = [
                (str(player.pk), f'{player.name} ({player.participant_id})')
                for player in players if player.pk in current or (
                    player.status == 'ACTIVE'
                    and (event.gender not in ('male', 'female') or player.gender == event.gender)
                    and (event.category == 'OPEN' or player.category == event.category)
                )
            ]
            self.fields[name] = forms.MultipleChoiceField(
                choices=choices, initial=initial, required=False, widget=forms.CheckboxSelectMultiple,
                label=f'{event.name} · {event.get_category_display()} · {event.get_gender_display()}',
            )
            self.event_rosters.append((event, self[name]))

    def clean(self):
        cleaned = super().clean()
        submitted = set(self.data.getlist('roster-event'))
        if submitted - self.fields.keys():
            raise forms.ValidationError('An event is no longer available. Review the event selections.')
        return {key: values for key, values in cleaned.items() if key in submitted}

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
