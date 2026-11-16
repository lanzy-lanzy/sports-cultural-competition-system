from django import forms

from participants.models import Participant
from teams.models import Team

from .models import EventEntry, Match, SportsEvent, SportType, Venue


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
            'cycles', 'playoff_count', 'grand_final_reset', 'best_of', 'group_count', 'qualifiers_per_group', 'win_points', 'draw_points', 'loss_points', 'bronze_policy', 'tiebreakers', 'rules', 'max_teams', 'venue', 'start_date', 'end_date', 'status',
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