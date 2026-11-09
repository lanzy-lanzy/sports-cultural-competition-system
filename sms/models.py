from django.conf import settings
from django.db import models


class SmsMessage(models.Model):
    """One outgoing SMS per recipient, including the Semaphore response."""

    class Category(models.TextChoices):
        TEST = 'TEST', 'Test message'
        MANUAL = 'MANUAL', 'Manual message'
        SCHEDULE = 'SCHEDULE', 'Schedule published'
        RESCHEDULE = 'RESCHEDULE', 'Schedule changed'
        REMINDER = 'REMINDER', 'Match reminder'
        MATCH_START = 'MATCH_START', 'Match live'
        RESULT = 'RESULT', 'Match result'

    class Status(models.TextChoices):
        SENT = 'SENT', 'Sent'
        FAILED = 'FAILED', 'Failed'
        SKIPPED = 'SKIPPED', 'Skipped'

    recipient = models.CharField(max_length=20, db_index=True)
    recipient_name = models.CharField(max_length=150, blank=True)
    body = models.TextField()
    sender_name = models.CharField(max_length=40, blank=True)
    category = models.CharField(
        max_length=20,
        choices=Category.choices,
        default=Category.MANUAL,
    )
    status = models.CharField(
        max_length=10,
        choices=Status.choices,
        default=Status.SENT,
    )
    semaphore_message_id = models.BigIntegerField(null=True, blank=True, db_index=True)
    provider_status = models.CharField(max_length=30, blank=True)
    error = models.TextField(blank=True)
    match = models.ForeignKey(
        'sports.Match',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='sms_messages',
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='sms_messages_sent',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at', '-id']
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['category']),
            models.Index(fields=['created_at']),
        ]

    def __str__(self):
        return f'{self.recipient} - {self.get_category_display()} ({self.get_status_display()})'

    @property
    def is_failed(self):
        return self.status == self.Status.FAILED
