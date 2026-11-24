import uuid

from django.conf import settings
from django.db import models

from participants.models import Participant


class Department(models.Model):
    code = models.CharField(
        max_length=30,
        unique=True,
        help_text='Short department code (e.g., SAFES, SOCJE, STE, SCS).',
    )
    name = models.CharField(
        max_length=150,
        blank=True,
        default='',
        help_text='Optional full department name.',
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['code']

    def save(self, *args, **kwargs):
        self.code = (self.code or '').strip().upper()
        self.name = (self.name or '').strip()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.code


class Team(models.Model):
    class Department(models.TextChoices):
        SAFES = 'SAFES', 'SAFES'
        SOCJE = 'SOCJE', 'SOCJE'
        STE = 'STE', 'STE'
        SCS = 'SCS', 'SCS'

    class Category(models.TextChoices):
        SPORTS = 'SPORTS', 'Sports Team'
        CULTURAL = 'CULTURAL', 'Cultural Delegation'
        MIXED = 'MIXED', 'Mixed Delegation'

    class Status(models.TextChoices):
        PENDING = 'PENDING', 'Pending approval'
        APPROVED = 'APPROVED', 'Approved'
        REJECTED = 'REJECTED', 'Rejected'
        SUSPENDED = 'SUSPENDED', 'Suspended'

    code = models.CharField(max_length=20, unique=True, editable=False)
    department = models.CharField(
        max_length=30,
        blank=True,
        default='',
        help_text='Academic department represented by this team.',
    )
    name = models.CharField(max_length=150, unique=True)
    category = models.CharField(max_length=20, choices=Category.choices)
    sports_categories = models.ManyToManyField('sports.SportType', blank=True, related_name='teams')
    description = models.TextField(blank=True)
    logo = models.ImageField(upload_to='team_logos/', blank=True, null=True)
    color_theme = models.CharField(
        max_length=20,
        blank=True,
        default='',
        help_text='Designated team color theme (hex code) selected by the team.',
    )
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    roster_submitted = models.BooleanField(default=False)
    roster_submitted_at = models.DateTimeField(null=True, blank=True)
    roster_submitted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='submitted_team_rosters',
    )
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
        if self.department:
            self.department = self.department.strip().upper()
        super().save(*args, **kwargs)

    def get_department_display(self):
        return self.department

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
    events = models.ManyToManyField(
        'sports.SportsEvent', blank=True, related_name='assigned_team_members',
        help_text='Sports events this roster member is assigned to.',
    )
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['team', 'member_number'], name='unique_team_member_number'),
        ]
        ordering = ['member_number', 'participant__name']

    def __str__(self):
        return f'{self.team} - {self.participant}'
