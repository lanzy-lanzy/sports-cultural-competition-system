from django.conf import settings
from django.db import models


class UserProfile(models.Model):
    class Role(models.TextChoices):
        ADMINISTRATOR = 'ADMINISTRATOR', 'System Administrator'
        EVENT_ORGANIZER = 'EVENT_ORGANIZER', 'Event Organizer'
        SPORTS_COORDINATOR = 'SPORTS_COORDINATOR', 'Sports Coordinator'
        CULTURAL_COORDINATOR = 'CULTURAL_COORDINATOR', 'Cultural Event Coordinator'
        TEAM_MANAGER = 'TEAM_MANAGER', 'Team Manager / Coach'
        PARTICIPANT = 'PARTICIPANT', 'Participant'
        JUDGE = 'JUDGE', 'Judge / Referee'
        SPECTATOR = 'SPECTATOR', 'Spectator'

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='account_profile',
    )
    role = models.CharField(max_length=30, choices=Role.choices, default=Role.SPECTATOR)
    middle_name = models.CharField(max_length=100, blank=True)
    phone = models.CharField(max_length=30, blank=True)
    profile_image = models.ImageField(upload_to='account_profiles/', blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['user__username']

    def __str__(self):
        return f'{self.user.username} - {self.get_role_display()}'

