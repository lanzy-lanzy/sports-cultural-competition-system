from django.conf import settings
from django.db import models

from competitions.models import Competition
from participants.models import Participant


class EligibilityRecord(models.Model):
    class Status(models.TextChoices):
        PENDING = 'PENDING', 'Pending review'
        APPROVED = 'APPROVED', 'Approved'
        REJECTED = 'REJECTED', 'Rejected'

    class Meta:
        ordering = ['-submitted_at']
        constraints = [
            models.UniqueConstraint(
                fields=['participant', 'competition'],
                name='unique_eligibility_participant_competition',
            ),
        ]

    participant = models.ForeignKey(
        Participant,
        on_delete=models.CASCADE,
        related_name='eligibility_records',
    )
    competition = models.ForeignKey(
        Competition,
        on_delete=models.CASCADE,
        related_name='eligibility_records',
    )
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    document = models.FileField(
        upload_to='eligibility_documents/%Y/%m/',
        null=True,
        blank=True,
        help_text='Proof of eligibility (medical clearance, school enrolment, etc.).',
    )
    notes = models.TextField(blank=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='eligibility_reviews',
    )
    submitted_at = models.DateTimeField(auto_now_add=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f'{self.participant.name} - {self.competition.name} ({self.get_status_display()})'
