from django.conf import settings
from django.db import models
from django.db.models import Q

from competitions.models import Competition
from sports.models import Match, SportsEvent


class Protest(models.Model):
    class Status(models.TextChoices):
        SUBMITTED = 'SUBMITTED', 'Submitted'
        UNDER_REVIEW = 'UNDER_REVIEW', 'Under review'
        RESOLVED = 'RESOLVED', 'Resolved'
        REJECTED = 'REJECTED', 'Rejected'

    class Meta:
        db_table = 'competition_app_protest'
        ordering = ['-submitted_at']
        constraints = [
            models.CheckConstraint(
                condition=(Q(competition__isnull=False) | Q(sport_event__isnull=False) | Q(match__isnull=False)),
                name='protest_has_target',
            ),
        ]

    submitter = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='protests',
    )
    competition = models.ForeignKey(
        Competition,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='protests',
    )
    sport_event = models.ForeignKey(
        SportsEvent,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='protests',
    )
    match = models.ForeignKey(
        Match,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='protests',
    )
    title = models.CharField(max_length=200)
    description = models.TextField(help_text='Explain the issue you are protesting or appealing.')
    supporting_document = models.FileField(
        upload_to='protest_documents/%Y/%m/',
        null=True,
        blank=True,
        help_text='Optional supporting evidence (PDF, image).',
    )
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.SUBMITTED)
    reviewers = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        related_name='protest_reviews',
        blank=True,
        help_text='Reviewing committee assigned to this protest.',
    )
    decision = models.TextField(blank=True, help_text='Resolution or reason for rejection.')
    submitted_at = models.DateTimeField(auto_now_add=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='protests_reviewed',
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f'{self.title} - {self.get_status_display()}'

    @property
    def target_name(self):
        if self.match_id:
            return f'{self.match.event.name} - {self.match.label}'
        if self.sport_event_id:
            return self.sport_event.name
        if self.competition_id:
            return self.competition.name
        return '—'

    @property
    def submitter_name(self):
        return self.submitter.get_full_name() or self.submitter.username