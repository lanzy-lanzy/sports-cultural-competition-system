from django.conf import settings
from django.db import models
from django.db.models import Q

from competitions.models import Competition
from participants.models import Participant
from teams.models import Team


class SportType(models.Model):
    class Meta:
        db_table = 'competition_app_sporttype'
        ordering = ['name']

    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    team_based = models.BooleanField(
        default=True,
        help_text='Team sport (basketball, volleyball) vs individual sport (chess, badminton).',
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class Venue(models.Model):
    class Meta:
        db_table = 'competition_app_venue'
        ordering = ['name']

    name = models.CharField(max_length=150)
    location = models.CharField(max_length=200, blank=True)
    capacity = models.PositiveIntegerField(null=True, blank=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class SportsEvent(models.Model):
    class Gender(models.TextChoices):
        MALE = 'male', 'Male'
        FEMALE = 'female', 'Female'
        MIXED = 'mixed', 'Mixed'
        OPEN = 'open', 'Open'

    class Category(models.TextChoices):
        JUNIOR = 'JUNIOR', 'Junior'
        OPEN_CATEGORY = 'OPEN', 'Open'
        SENIOR = 'SENIOR', 'Senior / Masters'

    class Format(models.TextChoices):
        SINGLE_ELIMINATION = 'SINGLE_ELIMINATION', 'Single elimination'
        DOUBLE_ELIMINATION = 'DOUBLE_ELIMINATION', 'Double elimination'
        ROUND_ROBIN = 'ROUND_ROBIN', 'Round robin'
        GROUP_STAGE = 'GROUP_STAGE', 'Group Stage + Knockout'
        KNOCKOUT = 'KNOCKOUT', 'Knockout (legacy)'
        BEST_OF = 'BEST_OF', 'Best-of Series'
        LEAGUE = 'LEAGUE', 'League Format'

    class Status(models.TextChoices):
        REGISTRATION = 'REGISTRATION', 'Registration'
        READY = 'READY', 'Ready'
        REVIEW = 'REVIEW', 'Awaiting confirmation'
        PLANNED = 'PLANNED', 'Planned'
        SCHEDULED = 'SCHEDULED', 'Scheduled'
        ONGOING = 'ONGOING', 'Ongoing'
        COMPLETED = 'COMPLETED', 'Completed'
        CANCELLED = 'CANCELLED', 'Cancelled'

    class Meta:
        db_table = 'competition_app_sportsevent'
        ordering = ['name']

    competition = models.ForeignKey(Competition, on_delete=models.CASCADE, related_name='sport_events')
    sport_type = models.ForeignKey(SportType, on_delete=models.PROTECT, related_name='events')
    name = models.CharField(max_length=200)
    category = models.CharField(max_length=20, choices=Category.choices, default=Category.OPEN_CATEGORY)
    gender = models.CharField(max_length=20, choices=Gender.choices, default=Gender.OPEN)
    team_based = models.BooleanField(default=True)
    format = models.CharField(max_length=20, choices=Format.choices, default=Format.SINGLE_ELIMINATION)
    cycles = models.PositiveSmallIntegerField(default=1, choices=[(1, 'Single round'), (2, 'Double round')])
    playoff_count = models.PositiveSmallIntegerField(default=0, choices=[(0, 'No playoffs'), (2, 'Top 2'), (4, 'Top 4'), (8, 'Top 8')])
    grand_final_reset = models.BooleanField(default=True)
    best_of = models.PositiveSmallIntegerField(default=3)
    group_count = models.PositiveSmallIntegerField(default=2)
    qualifiers_per_group = models.PositiveSmallIntegerField(default=2)
    win_points = models.PositiveSmallIntegerField(default=3)
    draw_points = models.PositiveSmallIntegerField(default=1)
    loss_points = models.PositiveSmallIntegerField(default=0)
    bronze_policy = models.CharField(max_length=10, default='SHARED', choices=[
        ('MATCH', 'Third-place match'), ('SHARED', 'Shared bronze'), ('NONE', 'No bronze'),
    ])
    tiebreakers = models.JSONField(default=list, blank=True)
    tie_resolution = models.JSONField(default=list, blank=True)
    confirmed_at = models.DateTimeField(null=True, blank=True)
    confirmed_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    rules = models.TextField(blank=True)
    max_teams = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text='Maximum number of participating teams or individuals.',
    )
    players_per_event = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        help_text='Required number of players per team/entry for this sport event.',
    )
    tournament_manager = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='managed_sport_events',
        help_text='Designated Tournament Manager authorized to record match scores for this sport event.',
    )
    venue = models.ForeignKey(Venue, on_delete=models.SET_NULL, null=True, blank=True, related_name='events')
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PLANNED)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

    @property
    def confirmed_count(self):
        return self.entries.filter(status=EventEntry.Status.CONFIRMED).count()

    def can_generate_bracket(self):
        return self.confirmed_count >= 2


class EventEntry(models.Model):
    class Status(models.TextChoices):
        PENDING = 'PENDING', 'Pending'
        CONFIRMED = 'CONFIRMED', 'Confirmed'
        WITHDRAWN = 'WITHDRAWN', 'Withdrawn'

    class Meta:
        db_table = 'competition_app_evententry'
        ordering = ['seed', 'id']
        constraints = [
            models.CheckConstraint(
                condition=(Q(team__isnull=False) & Q(participant__isnull=True))
                          | (Q(team__isnull=True) & Q(participant__isnull=False)),
                name='event_entry_single_contestant',
            ),
            # NULL never conflicts in a unique index on any supported backend,
            # so the isnull guards from the old conditional constraints are implicit.
            models.UniqueConstraint(fields=['event', 'team'], name='unique_event_team_entry'),
            models.UniqueConstraint(fields=['event', 'participant'], name='unique_event_participant_entry'),
        ]

    event = models.ForeignKey(SportsEvent, on_delete=models.CASCADE, related_name='entries')
    team = models.ForeignKey(Team, on_delete=models.CASCADE, null=True, blank=True, related_name='event_entries')
    participant = models.ForeignKey(
        Participant,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='event_entries',
    )
    seed = models.PositiveIntegerField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    registered_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'{self.event} - {self.display_name}'

    @property
    def display_name(self):
        if self.team_id:
            return self.team.name
        if self.participant_id:
            return self.participant.name
        return 'TBD'

    def save(self, *args, **kwargs):
        if self.seed is None:
            highest = self.event.entries.aggregate(models.Max('seed'))['seed__max'] or 0
            self.seed = highest + 1
        super().save(*args, **kwargs)


class Match(models.Model):
    class Status(models.TextChoices):
        SCHEDULED = 'SCHEDULED', 'Scheduled'
        ONGOING = 'ONGOING', 'Ongoing'
        COMPLETED = 'COMPLETED', 'Completed'
        POSTPONED = 'POSTPONED', 'Postponed'
        CANCELLED = 'CANCELLED', 'Cancelled'

    class Meta:
        db_table = 'competition_app_match'
        ordering = ['round_number', 'id']

    event = models.ForeignKey(SportsEvent, on_delete=models.CASCADE, related_name='matches')
    name = models.CharField(max_length=150, blank=True)
    round_number = models.PositiveIntegerField(default=1)
    group = models.CharField(
        max_length=50,
        null=True,
        blank=True,
        help_text='Group label (A, B, ...) for group-stage matches.',
    )
    venue = models.ForeignKey(Venue, on_delete=models.SET_NULL, null=True, blank=True, related_name='matches')
    scheduled_start = models.DateTimeField(null=True, blank=True)
    scheduled_end = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.SCHEDULED)
    next_match = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='previous_matches',
    )
    forfeited_side = models.PositiveSmallIntegerField(null=True, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        label = self.name or f'Round {self.round_number}'
        return f'{self.event.name} - {label}'

    @property
    def label(self):
        return self.name or f'Round {self.round_number}'

    @property
    def winner(self):
        return self.entries.filter(is_winner=True).first()

    def contestants_display(self):
        names = [entry.display_name for entry in self.entries.all()]
        return ' vs '.join(names) if names else 'TBD'


class MatchEntry(models.Model):
    class Meta:
        db_table = 'competition_app_matchentry'
        ordering = ['side']
        constraints = [
            models.CheckConstraint(
                condition=(Q(team__isnull=False) & Q(participant__isnull=True))
                          | (Q(team__isnull=True) & Q(participant__isnull=False)),
                name='match_entry_single_contestant',
            ),
            models.UniqueConstraint(fields=['match', 'side'], name='unique_match_side'),
        ]

    match = models.ForeignKey(Match, on_delete=models.CASCADE, related_name='entries')
    team = models.ForeignKey(Team, on_delete=models.CASCADE, null=True, blank=True, related_name='match_entries')
    participant = models.ForeignKey(
        Participant,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='match_entries',
    )
    side = models.PositiveIntegerField(default=1)
    score = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    is_winner = models.BooleanField(default=False)
    is_draw = models.BooleanField(default=False)

    def __str__(self):
        return f'{self.match} - side {self.side}'

    @property
    def display_name(self):
        if self.team_id:
            return self.team.name
        if self.participant_id:
            return self.participant.name
        return 'TBD'

class EventAward(models.Model):
    event = models.ForeignKey(SportsEvent, on_delete=models.CASCADE, related_name='confirmed_awards')
    entry = models.ForeignKey(EventEntry, on_delete=models.PROTECT)
    medal = models.CharField(max_length=6, choices=[('gold', 'Gold'), ('silver', 'Silver'), ('bronze', 'Bronze')])
    class Meta:
        constraints = [models.UniqueConstraint(fields=['event', 'entry'], name='unique_sports_award_entry')]
