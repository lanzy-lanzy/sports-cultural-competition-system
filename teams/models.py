import uuid

from django.conf import settings
from django.db import models

from participants.models import Participant


class Team(models.Model):
    class Category(models.TextChoices):
        SPORTS = 'SPORTS', 'Sports Team'
        CULTURAL = 'CULTURAL', 'Cultural Delegation'
        MIXED = 'MIXED', 'Mixed Delegation'

    class Status(models.TextChoices):
        PENDING = 'PENDING', 'Pending approval'
        APPROVED = 'APPROVED', 'Approved'
        SUSPENDED = 'SUSPENDED', 'Suspended'

    code = models.CharField(max_length=20, unique=True, editable=False)
    name = models.CharField(max_length=150, unique=True)
    category = models.CharField(max_length=20, choices=Category.choices)
    description = models.TextField(blank=True)
    logo = models.ImageField(upload_to='team_logos/', blank=True, null=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    members = models.ManyToManyField(Participant, through='TeamMembership', related_name='teams')
    staff = models.ManyToManyField(settings.AUTH_USER_MODEL, through='TeamStaff', related_name='competition_teams')
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='created_competition_teams',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']

    def save(self, *args, **kwargs):
        if not self.code:
            self.code = f'TEAM-{uuid.uuid4().hex[:8].upper()}'
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class TeamStaff(models.Model):
    class Role(models.TextChoices):
        COACH = 'COACH', 'Coach'
        MANAGER = 'MANAGER', 'Team Manager'

    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name='staff_assignments')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='team_staff_assignments')
    role = models.CharField(max_length=20, choices=Role.choices)
    assigned_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['team', 'user', 'role'], name='unique_team_staff_role'),
        ]
        ordering = ['role', 'user__last_name', 'user__first_name']

    def __str__(self):
        return f'{self.team} - {self.user} ({self.get_role_display()})'


class TeamMembership(models.Model):
    class Status(models.TextChoices):
        ACTIVE = 'ACTIVE', 'Active'
        INACTIVE = 'INACTIVE', 'Inactive'

    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name='memberships')
    participant = models.OneToOneField(
        Participant,
        on_delete=models.CASCADE,
        related_name='team_membership',
    )
    member_number = models.PositiveIntegerField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ACTIVE)
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['team', 'member_number'], name='unique_team_member_number'),
        ]
        ordering = ['member_number', 'participant__name']

    def __str__(self):
        return f'{self.team} - {self.participant}'
