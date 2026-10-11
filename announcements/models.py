from django.conf import settings
from django.db import models

from competitions.models import Competition


class Announcement(models.Model):
    class Audience(models.TextChoices):
        ALL = 'ALL', 'Everyone'
        MANAGEMENT = 'MANAGEMENT', 'Organizers'
        JUDGES = 'JUDGES', 'Judges'
        PARTICIPANTS = 'PARTICIPANTS', 'Participants'
        TEAM_MANAGERS = 'TEAM_MANAGERS', 'Team managers / coaches'

    class Meta:
        ordering = ['-created_at']

    title = models.CharField(max_length=200)
    body = models.TextField()
    competition = models.ForeignKey(
        Competition,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='announcements',
    )
    audience = models.CharField(max_length=20, choices=Audience.choices, default=Audience.ALL)
    is_published = models.BooleanField(default=False)
    published_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='announcements_created',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.title


class Notification(models.Model):
    class Meta:
        ordering = ['-created_at']

    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='notifications',
    )
    title = models.CharField(max_length=200)
    body = models.TextField(blank=True)
    link = models.CharField(max_length=300, blank=True)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'{self.recipient} - {self.title}'


class NotificationPreference(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='notification_preferences',
    )
    email_enabled = models.BooleanField(
        default=True,
        help_text='Receive email copies of system notifications and announcements.',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f'{self.user} - email {"on" if self.email_enabled else "off"}'
