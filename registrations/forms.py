from django import forms

from accounts.access import get_user_role
from accounts.models import UserProfile
from competitions.models import Competition
from sports.models import SportsEvent
from teams.models import Team


INPUT_CLASS = (
    'h-12 w-full rounded-xl border border-slate-200 bg-slate-50/70 px-4 '
    'text-sm text-slate-800 outline-none transition focus:border-campus '
    'focus:bg-white focus:ring-4 focus:ring-teal-100'
)


class EventRegistrationForm(forms.Form):
    target_type = forms.ChoiceField(
        choices=(
            ('sport_event', 'Sports'),
            ('competition', 'Socio Cultural'),
        ),
        initial='sport_event',
    )
    competition = forms.ModelChoiceField(
        queryset=Competition.objects.none(),
        required=False,
        empty_label='Select a socio cultural competition',
    )
    sport_event = forms.ChoiceField(choices=(), required=False)
    team = forms.ModelChoiceField(queryset=Team.objects.none(), required=False)

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        self.fields['competition'].queryset = (
            Competition.objects
            .filter(status='ACTIVE', kind=Competition.Kind.CULTURAL)
            .order_by('-id')
        )

        # Sports registrations stay synced with admin competition categories:
        # open SportsEvent rows under active non-cultural competitions, plus any
        # active Sports/Mixed competitions that do not yet have a SportsEvent.
        self.sport_events_queryset = (
            SportsEvent.objects
            .filter(
                competition__status='ACTIVE',
                status__in=[
                    SportsEvent.Status.PLANNED,
                    SportsEvent.Status.REGISTRATION,
                    SportsEvent.Status.SCHEDULED,
                ],
                matches__isnull=True,
            )
            .exclude(competition__kind=Competition.Kind.CULTURAL)
            .select_related('sport_type', 'competition')
            .order_by('competition__name', 'name')
        )
        self.sport_competitions_queryset = (
            Competition.objects
            .filter(status='ACTIVE', sport_events__isnull=True)
            .exclude(kind=Competition.Kind.CULTURAL)
            .order_by('-id')
        )

        self._sport_event_map = {str(event.pk): event for event in self.sport_events_queryset}
        self._sport_competition_map = {f'comp:{comp.pk}': comp for comp in self.sport_competitions_queryset}

        sport_choices = [('', 'Select a sports event or competition')]
        for event in self.sport_events_queryset:
            label = f'{event.name} ({event.competition.name})' if event.competition_id else event.name
            sport_choices.append((str(event.pk), label))
        for comp in self.sport_competitions_queryset:
            sport_choices.append((f'comp:{comp.pk}', comp.name))
        self.fields['sport_event'].choices = sport_choices

        # The team dropdown is only for team managers, who register a whole team
        # as one contestant. A participant's team comes from the "My team"
        # selection on their profile, so the dropdown is never shown to them.
        is_team_manager = user is not None and get_user_role(user) == UserProfile.Role.TEAM_MANAGER
        if is_team_manager:
            self.fields['team'].queryset = Team.objects.filter(
                staff_assignments__user=user,
            ).distinct().order_by('name')
        if not is_team_manager or not self.fields['team'].queryset.exists():
            self.fields.pop('team')
        elif is_team_manager:
            self.fields['team'].required = True
        for field in self.fields.values():
            field.widget.attrs['class'] = INPUT_CLASS

    def clean(self):
        cleaned = super().clean()
        if self.user and get_user_role(self.user) == UserProfile.Role.TEAM_MANAGER and 'team' not in self.fields:
            raise forms.ValidationError('Create a team or ask an organizer to assign you as team staff before registering.')
        target_type = cleaned.get('target_type')

        if target_type == 'competition':
            if not cleaned.get('competition'):
                self.add_error('competition', 'Select a socio cultural competition to register for.')
            cleaned['sport_event'] = None
        else:
            raw_sport = cleaned.get('sport_event')
            if not raw_sport:
                self.add_error('sport_event', 'Select a sports event or competition to register for.')
                cleaned['sport_event'] = None
                cleaned['competition'] = None
            elif raw_sport in self._sport_event_map:
                sport_event = self._sport_event_map[raw_sport]
                cleaned['sport_event'] = sport_event
                cleaned['competition'] = sport_event.competition
            elif raw_sport in self._sport_competition_map:
                cleaned['sport_event'] = None
                cleaned['competition'] = self._sport_competition_map[raw_sport]
            else:
                self.add_error('sport_event', 'Select a valid sports event or competition.')
                cleaned['sport_event'] = None
                cleaned['competition'] = None

        if cleaned.get('team'):
            from .models import EventRegistration
            if cleaned.get('sport_event'):
                if EventRegistration.objects.filter(team=cleaned['team'], sport_event=cleaned['sport_event']).exists():
                    self.add_error('team', 'This team already has a registration for this event. Check Team Registrations for its status.')
            elif cleaned.get('competition'):
                if EventRegistration.objects.filter(
                    team=cleaned['team'],
                    competition=cleaned['competition'],
                    sport_event__isnull=True,
                ).exists():
                    self.add_error('team', 'This team already has a registration for this competition. Check Team Registrations for its status.')
        return cleaned
