from django import forms

from participants.models import Participant
from teams.models import Team

from .models import EventEntry, Match, MatchEntry, SportsEvent, SportType, Venue


INPUT_CLASS = (
    'h-12 w-full rounded-xl border border-slate-200 bg-slate-50/70 px-4 '
    'text-sm text-slate-800 outline-none transition focus:border-campus '
    'focus:bg-white focus:ring-4 focus:ring-teal-100'
)
TEXTAREA_CLASS = INPUT_CLASS.replace('h-12', 'min-h-28')


def _style_fields(form):
    for field in form.fields.values():
        if isinstance(field.widget, forms.Textarea):
            field.widget.attrs['class'] = TEXTAREA_CLASS
        else:
            field.widget.attrs['class'] = INPUT_CLASS
    return form


class SportTypeForm(forms.ModelForm):
    class Meta:
        model = SportType
        fields = ('name', 'description', 'team_based', 'is_active')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _style_fields(self)


class VenueForm(forms.ModelForm):
    class Meta:
        model = Venue
        fields = ('name', 'location', 'capacity', 'description', 'is_active')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _style_fields(self)


class SportsEventForm(forms.ModelForm):
    TIEBREAK_ORDERS = {
        'DIFFERENCE': ['point_diff', 'points_for'],
        'HEAD_TO_HEAD': ['head_to_head', 'point_diff', 'points_for'],
        'SCORED': ['points_for', 'point_diff', 'head_to_head'],
    }
    tiebreakers = forms.ChoiceField(label='Tie-breaker order', choices=[
        ('DIFFERENCE', 'Score difference, then scores recorded'),
        ('HEAD_TO_HEAD', 'Head-to-head, score difference, then scores recorded'),
        ('SCORED', 'Scores recorded, score difference, then head-to-head'),
    ])

    def clean_tiebreakers(self):
        return self.TIEBREAK_ORDERS[self.cleaned_data['tiebreakers']]

    class Meta:
        model = SportsEvent
        fields = (
            'sport_type', 'name', 'category', 'gender', 'team_based', 'format',
            'cycles', 'playoff_count', 'grand_final_reset', 'best_of', 'group_count', 'qualifiers_per_group', 'win_points', 'draw_points', 'loss_points', 'bronze_policy', 'tiebreakers', 'rules', 'max_teams', 'players_per_event', 'tournament_manager', 'venue', 'start_date', 'end_date', 'status',
        )
        widgets = {
            'rules': forms.Textarea(attrs={'rows': 4}),
            'start_date': forms.DateInput(attrs={'type': 'date'}),
            'end_date': forms.DateInput(attrs={'type': 'date'}),
        }

    def __init__(self, *args, **kwargs):
        if args and args[0] is not None:
            data = args[0].copy()
            if data.get('team_based') in ('off', 'false', '0'):
                data['team_based'] = ''
            for key in ('cycles', 'playoff_count', 'best_of', 'group_count', 'qualifiers_per_group', 'win_points', 'draw_points', 'loss_points', 'bronze_policy'):
                if key not in data:
                    data[key] = str(SportsEvent._meta.get_field(key).default)
            if 'tiebreakers' not in data:
                data['tiebreakers'] = 'DIFFERENCE'
            args = (data, *args[1:])
        super().__init__(*args, **kwargs)
        self.fields['sport_type'].queryset = SportType.objects.filter(is_active=True)
        self.fields['venue'].queryset = Venue.objects.filter(is_active=True)
        self.fields['venue'].required = False
        from django.contrib.auth import get_user_model
        from django.db.models import Q
        from accounts.models import UserProfile
        User = get_user_model()
        tm_q = Q(is_active=True, account_profile__role=UserProfile.Role.TOURNAMENT_MANAGER)
        if self.instance.tournament_manager_id:
            tm_q |= Q(pk=self.instance.tournament_manager_id)
        self.fields['tournament_manager'].queryset = User.objects.filter(tm_q).distinct().order_by('first_name', 'last_name', 'username')
        self.fields['tournament_manager'].required = False
        self.fields['tournament_manager'].label_from_instance = lambda u: f'{u.get_full_name() or u.username} ({u.username})'
        # The view names the event after the sport type and division when the
        # name is left blank, so keep the form permissive about it.
        self.fields['name'].required = False
        stored = self.instance.tiebreakers or self.TIEBREAK_ORDERS['DIFFERENCE']
        self.initial['tiebreakers'] = next((key for key, value in self.TIEBREAK_ORDERS.items() if value == stored), 'DIFFERENCE')
        if self.instance.format != SportsEvent.Format.KNOCKOUT:
            self.fields['format'].choices = [(k, v) for k, v in SportsEvent.Format.choices if k != SportsEvent.Format.KNOCKOUT]
        self.fields['status'].choices = [(k, v) for k, v in SportsEvent.Status.choices if k not in ('COMPLETED', 'REVIEW')]
        if self.instance.pk:
            self.fields['status'].choices = SportsEvent.Status.choices
            self.fields['status'].disabled = True
            if self.instance.matches.exists():
                for key in ('sport_type', 'team_based', 'format', 'cycles', 'playoff_count', 'grand_final_reset', 'best_of', 'group_count', 'qualifiers_per_group', 'win_points', 'draw_points', 'loss_points', 'bronze_policy', 'tiebreakers'):
                    self.fields[key].disabled = True
        self.fields['tiebreakers'].help_text = 'Applied in order after standings points. Remaining ties require a recorded coordinator decision.'
        _style_fields(self)

    def clean(self):
        cleaned = super().clean()
        best = cleaned.get('best_of')
        if best is not None and (best < 1 or best > 15 or best % 2 == 0):
            self.add_error('best_of', 'Use an odd number from 1 to 15.')
        for key in ('group_count', 'qualifiers_per_group'):
            if cleaned.get(key) is not None and cleaned[key] < 1:
                self.add_error(key, 'Must be at least one.')
        breakers = cleaned.get('tiebreakers') or []
        if not isinstance(breakers, list) or any(x not in ('head_to_head', 'point_diff', 'points_for') for x in breakers) or len(set(breakers)) != len(breakers):
            self.add_error('tiebreakers', 'Use a list of unique supported tie-breakers.')
        start = cleaned.get('start_date')
        end = cleaned.get('end_date')
        venue = cleaned.get('venue')
        if start and end and end < start:
            self.add_error('end_date', 'End date cannot be before the start date.')
        if venue and start and end:
            conflicts = SportsEvent.objects.filter(
                venue=venue,
                status__in=[SportsEvent.Status.PLANNED, SportsEvent.Status.SCHEDULED, SportsEvent.Status.ONGOING],
                start_date__lt=end,
                end_date__gt=start,
            ).exclude(id=self.instance.pk)
            if conflicts.exists():
                names = ', '.join(conflict.name for conflict in conflicts[:3])
                self.add_error(
                    'venue',
                    f'This venue already hosts another event during the selected dates: {names}.',
                )
        return cleaned


class EventEntryForm(forms.Form):
    CHOICE_NONE = ('', '---------')

    contestant_type = forms.ChoiceField(
        choices=(('team', 'Team / Delegation'), ('participant', 'Individual Participant')),
    )
    team = forms.ModelChoiceField(queryset=Team.objects.none(), required=False)
    participant = forms.ModelChoiceField(queryset=Participant.objects.none(), required=False)

    def __init__(self, *args, event, **kwargs):
        super().__init__(*args, **kwargs)
        self.event = event
        taken_team_ids = event.entries.exclude(team__isnull=True).values_list('team_id', flat=True)
        taken_participant_ids = event.entries.exclude(participant__isnull=True).values_list('participant_id', flat=True)
        self.fields['team'].queryset = Team.objects.filter(
            status=Team.Status.APPROVED,
        ).exclude(id__in=taken_team_ids).order_by('name')
        self.fields['participant'].queryset = Participant.objects.filter(
            status='ACTIVE',
        ).exclude(id__in=taken_participant_ids).order_by('name')
        for field in self.fields.values():
            field.widget.attrs['class'] = INPUT_CLASS

    def clean(self):
        cleaned = super().clean()
        contestant_type = cleaned.get('contestant_type')
        if self.event.matches.exists():
            raise forms.ValidationError('Entries are locked after fixture generation.')
        if self.event.max_teams and self.event.entries.exclude(status='WITHDRAWN').count() >= self.event.max_teams:
            raise forms.ValidationError('This event has reached its entry cap.')
        if (contestant_type == 'team') != self.event.team_based:
            raise forms.ValidationError('The contestant type must match the event team/individual setting.')
        if contestant_type == 'team':
            if not cleaned.get('team'):
                self.add_error('team', 'Select a team for this event.')
            cleaned['participant'] = None
        else:
            if not cleaned.get('participant'):
                self.add_error('participant', 'Select a participant for this event.')
            cleaned['team'] = None
        return cleaned


class MatchForm(forms.ModelForm):
    class Meta:
        model = Match
        fields = ('name', 'round_number', 'venue', 'scheduled_start', 'scheduled_end', 'status', 'notes')
        widgets = {
            'scheduled_start': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
            'scheduled_end': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
            'notes': forms.Textarea(attrs={'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['venue'].queryset = Venue.objects.filter(is_active=True)
        self.fields['venue'].required = False
        self.fields['round_number'].required = False
        self.fields['round_number'].disabled = True
        self.fields['name'].disabled = True
        self.fields['status'].choices = [(k, v) for k, v in Match.Status.choices if k != 'COMPLETED']
        if self.instance.status == 'COMPLETED' or self.instance.event.status in ('COMPLETED', 'CANCELLED'):
            self.fields['status'].choices = Match.Status.choices
            self.fields['status'].disabled = True
        _style_fields(self)

    def clean(self):
        cleaned = super().clean()
        start = cleaned.get('scheduled_start')
        end = cleaned.get('scheduled_end')
        if start and end and end <= start:
            self.add_error('scheduled_end', 'End time must be after the start time.')
        venue = cleaned.get('venue')
        if venue and start and end:
            from .services import find_venue_conflicts
            conflicts = find_venue_conflicts(venue, start, end, exclude_id=self.instance.pk)
            if conflicts:
                labels = ', '.join(
                    f'{conflict.event.name} - {conflict.label}' for conflict in conflicts[:3]
                )
                self.add_error(
                    'venue',
                    f'This venue is already scheduled during that time: {labels}.',
                )
        return cleaned


class ManualMatchForm(MatchForm):
    adjust_pairings = forms.BooleanField(
        required=False, label='Replace opponents',
        help_text='Select this to replace the two opponents. Otherwise the current pairing is preserved.',
    )
    opponent_1 = forms.ModelChoiceField(queryset=EventEntry.objects.none(), required=False)
    opponent_2 = forms.ModelChoiceField(queryset=EventEntry.objects.none(), required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.creating = self.instance.pk is None
        entries = self.instance.event.entries.filter(status=EventEntry.Status.CONFIRMED)
        entries = entries.filter(participant__isnull=True) if self.instance.event.team_based else entries.filter(team__isnull=True)
        entries = entries.select_related('team', 'participant')
        for name in ('opponent_1', 'opponent_2'):
            self.fields[name].queryset = entries
            self.fields[name].label_from_instance = lambda entry: entry.display_name
        if self.creating:
            self.fields.pop('adjust_pairings')
            self.fields['name'].disabled = False
            self.fields['round_number'].disabled = False
            self.fields['round_number'].required = True
            self.fields['opponent_1'].required = True
            self.fields['opponent_2'].required = True
        else:
            current = {entry.side: entry for entry in self.instance.entries.all()}
            for side in (1, 2):
                contestant = current.get(side)
                if contestant:
                    entry = entries.filter(team_id=contestant.team_id, participant_id=contestant.participant_id).first()
                    self.initial[f'opponent_{side}'] = entry.pk if entry else None
        # datetime-local controls require an ISO local value to retain saved times.
        for name in ('scheduled_start', 'scheduled_end'):
            self.fields[name].widget.format = '%Y-%m-%dT%H:%M'
        _style_fields(self)
        if 'adjust_pairings' in self.fields:
            self.fields['adjust_pairings'].widget.attrs['class'] = 'h-4 w-4 rounded border-slate-300'

    def clean(self):
        cleaned = super().clean()
        event = self.instance.event
        if event.confirmed_at or event.status in ('COMPLETED', 'CANCELLED'):
            raise forms.ValidationError('This event is closed. Reopen it before changing matches.')
        if bool(cleaned.get('scheduled_start')) != bool(cleaned.get('scheduled_end')):
            raise forms.ValidationError('Provide both start and end times, or leave both blank.')
        if cleaned.get('round_number', 1) is not None and cleaned.get('round_number', 1) < 1:
            self.add_error('round_number', 'Round must be at least 1.')
        if self.creating or cleaned.get('adjust_pairings'):
            if not self.creating and (
                self.instance.status in ('ONGOING', 'COMPLETED')
                or self.instance.entries.filter(score__isnull=False).exists()
                or self.instance.entries.filter(is_winner=True).exists()
                or self.instance.previous_matches.exists()
            ):
                raise forms.ValidationError(
                    'Opponents cannot be replaced after play starts, results are recorded, '
                    'or when they are determined by earlier bracket matches.',
                )
            first, second = cleaned.get('opponent_1'), cleaned.get('opponent_2')
            if not first or not second:
                raise forms.ValidationError('Choose two confirmed event entries to assign opponents.')
            if first == second:
                self.add_error('opponent_2', 'A contestant cannot play against itself.')
        return cleaned

    def save(self, commit=True):
        if not commit:
            raise ValueError('Manual matches must be saved with their opponents.')
        from django.db import transaction
        with transaction.atomic():
            match = super().save()
            if self.creating or self.cleaned_data.get('adjust_pairings'):
                match.entries.all().delete()
                for side in (1, 2):
                    opponent = self.cleaned_data[f'opponent_{side}']
                    MatchEntry.objects.create(
                        match=match, side=side, team_id=opponent.team_id,
                        participant_id=opponent.participant_id,
                    )
            return match


class BoardManualMatchForm(forms.Form):
    """Single-page Match Board form: pick any two teams (or participants) to play
    versus each other and schedule the match in one step, auto-enrolling entries
    if they are not yet on the event roster."""

    opponent_1 = forms.ChoiceField(label='Team 1', choices=())
    opponent_2 = forms.ChoiceField(label='Team 2', choices=())
    name = forms.CharField(
        max_length=150,
        required=False,
        label='Match name',
        widget=forms.TextInput(attrs={'placeholder': 'e.g. Game 1, Semifinal, Exhibition'}),
    )
    round_number = forms.IntegerField(min_value=1, initial=1, label='Round')
    venue = forms.ModelChoiceField(
        queryset=Venue.objects.none(),
        required=False,
        empty_label='No venue assigned',
    )
    scheduled_start = forms.DateTimeField(
        required=False,
        label='Start time',
        input_formats=['%Y-%m-%dT%H:%M', '%Y-%m-%d %H:%M:%S', '%Y-%m-%d %H:%M'],
        widget=forms.DateTimeInput(attrs={'type': 'datetime-local'}, format='%Y-%m-%dT%H:%M'),
    )
    scheduled_end = forms.DateTimeField(
        required=False,
        label='End time',
        input_formats=['%Y-%m-%dT%H:%M', '%Y-%m-%d %H:%M:%S', '%Y-%m-%d %H:%M'],
        widget=forms.DateTimeInput(attrs={'type': 'datetime-local'}, format='%Y-%m-%dT%H:%M'),
    )
    status = forms.ChoiceField(
        choices=[(k, v) for k, v in Match.Status.choices if k != Match.Status.COMPLETED],
        initial=Match.Status.SCHEDULED,
    )
    notes = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={'rows': 2, 'placeholder': 'Optional court notes, referee details, or reminders'}),
    )

    def __init__(self, *args, event=None, team_based=True, **kwargs):
        super().__init__(*args, **kwargs)
        self.event = event
        self.team_based = event.team_based if event is not None else team_based
        self.fields['venue'].queryset = Venue.objects.filter(is_active=True).order_by('name')
        if event is not None and event.venue_id and not self.is_bound:
            self.initial['venue'] = event.venue_id

        self._contestant_map = {}
        self._entry_id_map = {}

        if self.team_based:
            self.fields['opponent_1'].label = 'Team 1'
            self.fields['opponent_2'].label = 'Team 2'
            entered_team_ids = set()
            if event is not None:
                for entry in event.entries.filter(
                    status=EventEntry.Status.CONFIRMED, team__isnull=False,
                ).select_related('team'):
                    entered_team_ids.add(entry.team_id)
                    self._entry_id_map[str(entry.pk)] = ('team', entry.team)

            teams = list(Team.objects.exclude(status=Team.Status.SUSPENDED).order_by('name'))
            entered_choices = []
            other_choices = []
            for team in teams:
                key = f'team:{team.pk}'
                self._contestant_map[key] = ('team', team)
                if team.pk in entered_team_ids:
                    entered_choices.append((key, f'{team.name} (In event)'))
                else:
                    other_choices.append((key, team.name))

            choices = [('', 'Select a team...')]
            if entered_choices and other_choices:
                choices.append(('Already in this event', entered_choices))
                choices.append(('All other teams', other_choices))
            else:
                choices.extend(entered_choices or other_choices)
            self.available_contestants_count = len(teams)
        else:
            self.fields['opponent_1'].label = 'Participant 1'
            self.fields['opponent_2'].label = 'Participant 2'
            entered_participant_ids = set()
            if event is not None:
                for entry in event.entries.filter(
                    status=EventEntry.Status.CONFIRMED, participant__isnull=False,
                ).select_related('participant'):
                    entered_participant_ids.add(entry.participant_id)
                    self._entry_id_map[str(entry.pk)] = ('participant', entry.participant)

            participants = list(Participant.objects.filter(status='ACTIVE').order_by('name'))
            entered_choices = []
            other_choices = []
            for person in participants:
                key = f'participant:{person.pk}'
                self._contestant_map[key] = ('participant', person)
                if person.pk in entered_participant_ids:
                    entered_choices.append((key, f'{person.name} (In event)'))
                else:
                    other_choices.append((key, person.name))

            choices = [('', 'Select a participant...')]
            if entered_choices and other_choices:
                choices.append(('Already in this event', entered_choices))
                choices.append(('All other participants', other_choices))
            else:
                choices.extend(entered_choices or other_choices)
            self.available_contestants_count = len(participants)

        # Also accept legacy plain EventEntry PKs in POST submissions.
        valid_choice_list = list(choices)
        if self.is_bound and self._entry_id_map:
            for entry_pk, (_, obj) in self._entry_id_map.items():
                valid_choice_list.append((entry_pk, obj.name))

        for field_name in ('opponent_1', 'opponent_2'):
            self.fields[field_name].choices = valid_choice_list if self.is_bound else choices

        _style_fields(self)

    def _resolve_opponent(self, raw_value):
        if raw_value in self._contestant_map:
            return self._contestant_map[raw_value]
        if raw_value in self._entry_id_map:
            return self._entry_id_map[raw_value]
        return None

    def clean(self):
        cleaned = super().clean()
        if self.event is not None and (
            self.event.confirmed_at or self.event.status in (SportsEvent.Status.COMPLETED, SportsEvent.Status.CANCELLED)
        ):
            raise forms.ValidationError('This event is closed. Reopen it before adding matches.')

        start = cleaned.get('scheduled_start')
        end = cleaned.get('scheduled_end')
        if bool(start) != bool(end):
            raise forms.ValidationError('Provide both start and end times, or leave both blank.')
        if start and end and end <= start:
            self.add_error('scheduled_end', 'End time must be after the start time.')

        venue = cleaned.get('venue')
        if venue and start and end:
            from .services import find_venue_conflicts
            conflicts = find_venue_conflicts(venue, start, end)
            if conflicts:
                labels = ', '.join(f'{c.event.name} - {c.label}' for c in conflicts[:3])
                self.add_error('venue', f'This venue is already scheduled during that time: {labels}.')

        opp1 = self._resolve_opponent(cleaned.get('opponent_1'))
        opp2 = self._resolve_opponent(cleaned.get('opponent_2'))
        if not opp1:
            self.add_error('opponent_1', 'Select the first contestant.')
        if not opp2:
            self.add_error('opponent_2', 'Select the second contestant.')
        if opp1 and opp2 and opp1[0] == opp2[0] and opp1[1].pk == opp2[1].pk:
            self.add_error('opponent_2', 'A contestant cannot play against itself.')

        cleaned['resolved_opponent_1'] = opp1
        cleaned['resolved_opponent_2'] = opp2
        return cleaned

    def save(self, event):
        from django.db import transaction

        with transaction.atomic():
            match = Match.objects.create(
                event=event,
                name=(self.cleaned_data.get('name') or '').strip(),
                round_number=self.cleaned_data.get('round_number') or 1,
                venue=self.cleaned_data.get('venue'),
                scheduled_start=self.cleaned_data.get('scheduled_start'),
                scheduled_end=self.cleaned_data.get('scheduled_end'),
                status=self.cleaned_data.get('status') or Match.Status.SCHEDULED,
                notes=self.cleaned_data.get('notes') or '',
            )
            for side, key in ((1, 'resolved_opponent_1'), (2, 'resolved_opponent_2')):
                kind, obj = self.cleaned_data[key]
                if kind == 'team':
                    entry, created = EventEntry.objects.get_or_create(
                        event=event,
                        team=obj,
                        defaults={'status': EventEntry.Status.CONFIRMED},
                    )
                    if not created and entry.status != EventEntry.Status.CONFIRMED:
                        entry.status = EventEntry.Status.CONFIRMED
                        entry.save(update_fields=['status'])
                    MatchEntry.objects.create(match=match, side=side, team=obj)
                else:
                    entry, created = EventEntry.objects.get_or_create(
                        event=event,
                        participant=obj,
                        defaults={'status': EventEntry.Status.CONFIRMED},
                    )
                    if not created and entry.status != EventEntry.Status.CONFIRMED:
                        entry.status = EventEntry.Status.CONFIRMED
                        entry.save(update_fields=['status'])
                    MatchEntry.objects.create(match=match, side=side, participant=obj)
            return match
