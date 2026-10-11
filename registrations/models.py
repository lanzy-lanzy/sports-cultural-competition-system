from django.conf import settings
from django.db import models
from django.db.models import Q

from competitions.models import Competition
from participants.models import Participant
from sports.models import SportsEvent
from teams.models import Team


class EventRegistration(models.Model):
    class Status(models.TextChoices):
        PENDING = 'PENDING', 'Pending approval'
        UNDER_REVIEW = 'UNDER_REVIEW', 'Under Review'
        APPROVED = 'APPROVED', 'Approved'
        REJECTED = 'REJECTED', 'Rejected'

    class Meta:
        ordering = ['-created_at']
        constraints = [
            models.CheckConstraint(
                condition=(Q(team__isnull=False) & Q(participant__isnull=True))
                          | (Q(team__isnull=True) & Q(participant__isnull=False)),
                name='registration_single_contestant',
            ),
            models.CheckConstraint(
                condition=(Q(competition__isnull=False) | Q(sport_event__isnull=False)),
                name='registration_has_target',
            ),
            models.UniqueConstraint(fields=['sport_event', 'team'], name='unique_registration_sport_event_team'),
            models.UniqueConstraint(fields=['sport_event', 'participant'], name='unique_registration_sport_event_participant'),
            models.UniqueConstraint(fields=['competition', 'participant'], name='unique_registration_competition_participant'),
        ]

    registrant = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='event_registrations',
    )
    competition = models.ForeignKey(
        Competition,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='registrations',
    )
    sport_event = models.ForeignKey(
        SportsEvent,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='registrations',
    )
    team = models.ForeignKey(
        Team,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='registrations',
    )
    participant = models.ForeignKey(
        Participant,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='registrations',
    )
    requirements_document = models.FileField(
        upload_to='registration_requirements/%Y/%m/',
        null=True,
        blank=True,
        help_text='Optional requirements such as waiver forms or clearances.',
    )
    notes = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='registration_reviews',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        target = self.sport_event or self.competition
        return f'{self.contestant_name} - {target} ({self.get_status_display()})'

    @property
    def contestant_name(self):
        if self.team_id:
            return self.team.name
        if self.participant_id:
            return self.participant.name
        return self.registrant.get_full_name() or self.registrant.username

    @property
    def target_name(self):
        if self.sport_event_id:
            return f'{self.sport_event.name} (sport)'
        if self.competition_id:
            return self.competition.name
        return '—'
