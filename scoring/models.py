from django.conf import settings
from django.db import models
from django.db.models import Q

from participants.models import Participant
from competitions.models import Competition, Criterion, Round
from judges.models import Judge
from teams.models import Team


class Score(models.Model):
    class Meta:
        db_table = 'competition_app_score'
        unique_together = ['participant', 'criterion', 'judge']

    participant = models.ForeignKey(Participant, on_delete=models.CASCADE, related_name='scores')
    criterion = models.ForeignKey(Criterion, on_delete=models.CASCADE, related_name='scores')
    judge = models.ForeignKey(Judge, on_delete=models.CASCADE, related_name='scores')
    score = models.DecimalField(max_digits=5, decimal_places=2)
    remarks = models.TextField(blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=[
        ('DRAFT', 'Draft'),
        ('SUBMITTED', 'Submitted'),
        ('VERIFIED', 'Verified')
    ], default='DRAFT')

    def __str__(self):
        return f"{self.participant} - {self.criterion} - {self.judge}"


class ScoreChangeLog(models.Model):
    """Immutable audit record of every change made to an individual score."""

    class Action(models.TextChoices):
        DRAFT_UPDATE = 'DRAFT_UPDATE', 'Draft edit'
        SUBMITTED = 'SUBMITTED', 'Submitted'
        VERIFIED = 'VERIFIED', 'Verified'
        UNVERIFIED = 'UNVERIFIED', 'Verification cleared'

    class Meta:
        db_table = 'competition_app_scorechangelog'
        ordering = ['-created_at', '-id']

    score = models.ForeignKey(
        Score,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='change_logs',
        help_text='The score this change applied to. Kept as null if the score row was later deleted.',
    )
    participant = models.ForeignKey(Participant, on_delete=models.CASCADE, related_name='score_changes')
    criterion = models.ForeignKey(Criterion, on_delete=models.SET_NULL, null=True, blank=True, related_name='score_changes')
    judge = models.ForeignKey(Judge, on_delete=models.SET_NULL, null=True, blank=True, related_name='score_changes')
    competition = models.ForeignKey(Competition, on_delete=models.CASCADE, related_name='score_changes')
    round = models.ForeignKey(Round, on_delete=models.SET_NULL, null=True, blank=True, related_name='score_changes')
    action = models.CharField(max_length=20, choices=Action.choices, default=Action.DRAFT_UPDATE)
    old_score = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    new_score = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    old_status = models.CharField(max_length=20, blank=True)
    new_status = models.CharField(max_length=20, blank=True)
    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='score_changes_made',
    )
    details = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'{self.participant} / {self.criterion} {self.old_score} -> {self.new_score}'


class CompetitionResult(models.Model):
    class Meta:
        db_table = 'competition_app_competitionresult'
        unique_together = ['competition', 'participant', 'round']

    competition = models.ForeignKey(Competition, on_delete=models.CASCADE, related_name='results')
    participant = models.ForeignKey(Participant, on_delete=models.CASCADE, related_name='results')
    round = models.ForeignKey(Round, on_delete=models.CASCADE, related_name='results')
    total_score = models.DecimalField(max_digits=10, decimal_places=2)
    rank = models.PositiveIntegerField()
    timestamp = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.participant} - {self.competition} - {self.round}"


class Award(models.Model):
    class Type(models.TextChoices):
        GOLD_MEDAL = 'GOLD_MEDAL', 'Gold medal'
        SILVER_MEDAL = 'SILVER_MEDAL', 'Silver medal'
        BRONZE_MEDAL = 'BRONZE_MEDAL', 'Bronze medal'
        MVP = 'MVP', 'Most Valuable Player'
        CERTIFICATE = 'CERTIFICATE', 'Certificate of recognition'
        TROPHY = 'TROPHY', 'Trophy'
        OTHER = 'OTHER', 'Other award'

    class Meta:
        db_table = 'competition_app_award'
        ordering = ['rank', 'name']

    competition = models.ForeignKey(Competition, on_delete=models.CASCADE, related_name='awards')
    name = models.CharField(max_length=200)
    type = models.CharField(max_length=20, choices=Type.choices, default=Type.CERTIFICATE)
    description = models.TextField(blank=True)
    rank = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text='Overall placement (1, 2, 3). Optional.',
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name


class AwardRecipient(models.Model):
    class RecipientType(models.TextChoices):
        PARTICIPANT = 'PARTICIPANT', 'Participant'
        TEAM = 'TEAM', 'Team / Delegation'

    class Meta:
        db_table = 'competition_app_awardrecipient'
        ordering = ['award', 'id']
        constraints = [
            models.CheckConstraint(
                condition=(Q(participant__isnull=False) & Q(team__isnull=True))
                          | (Q(participant__isnull=True) & Q(team__isnull=False)),
                name='award_recipient_single_contestant',
            ),
            models.UniqueConstraint(fields=['award', 'participant'], name='unique_award_participant'),
            models.UniqueConstraint(fields=['award', 'team'], name='unique_award_team'),
        ]

    award = models.ForeignKey(Award, on_delete=models.CASCADE, related_name='recipients')
    recipient_type = models.CharField(max_length=20, choices=RecipientType.choices, default=RecipientType.PARTICIPANT)
    participant = models.ForeignKey(
        Participant,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='award_recipients',
    )
    team = models.ForeignKey(
        Team,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='award_recipients',
    )
    citation = models.TextField(blank=True)
    awarded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'{self.award} - {self.display_name}'

    @property
    def display_name(self):
        if self.team_id:
            return self.team.name
        if self.participant_id:
            return self.participant.name
        return 'TBD'
