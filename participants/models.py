import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from competitions.models import Competition


class Participant(models.Model):
    class Category(models.TextChoices):
        JUNIOR = 'JUNIOR', 'Junior'
        OPEN = 'OPEN', 'Open'
        SENIOR = 'SENIOR', 'Senior / Masters'

    class Meta:
        db_table = 'competition_app_participant'

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name='participant_profile',
        null=True,
        blank=True,
    )
    participant_id = models.CharField(max_length=20, unique=True, editable=False)
    competitions = models.ManyToManyField(Competition, related_name='participants', through='ParticipantCompetition')
    name = models.CharField(max_length=200)
    profile_image = models.ImageField(upload_to='participant_profiles/', null=True, blank=True)
    email = models.EmailField(blank=True, null=True, unique=True)
    phone = models.CharField(max_length=20)
    age = models.PositiveIntegerField(null=True, blank=True)
    birth_date = models.DateField(null=True, blank=True)
    category = models.CharField(max_length=20, choices=Category.choices, default=Category.OPEN)
    team_name = models.CharField(max_length=150, blank=True, verbose_name='Team / delegation')
    gender = models.CharField(max_length=20, choices=[
        ('male', 'Male'),
        ('female', 'Female'),
        ('other', 'Other'),
        ('prefer_not_to_say', 'Prefer not to say')
    ], default='prefer_not_to_say')
    bio = models.TextField(blank=True)
    achievements = models.TextField(blank=True)
    registration_date = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=[
        ('ACTIVE', 'Active'),
        ('WITHDRAWN', 'Withdrawn'),
        ('ELIMINATED', 'Eliminated')
    ], default='ACTIVE')
    performance_metrics = models.TextField(blank=True)
    identification_number = models.CharField(
        max_length=100,
        blank=True,
        verbose_name='School ID number',
    )

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.participant_id:
            self.participant_id = f'JHCSC-{uuid.uuid4().hex[:10].upper()}'
        super().save(*args, **kwargs)

    def clean(self):
        super().clean()
        if self.age is not None and self.age > 120:
            raise ValidationError({'age': 'Enter a valid participant age.'})

    @property
    def age_classification(self):
        if self.age is None:
            return 'Unclassified'
        if self.age < 18:
            return 'Youth'
        if self.age < 40:
            return 'Adult'
        return 'Masters'

    def clean_gender(self):
        if self.gender not in ['male', 'female', 'other', 'prefer_not_to_say']:
            raise ValueError("Invalid gender")


class ParticipantCompetition(models.Model):
    class Meta:
        db_table = 'competition_app_participantcompetition'
        unique_together = ['competition', 'number']
        constraints = [
            models.UniqueConstraint(
                fields=['participant', 'competition'],
                name='unique_participant_per_competition',
            ),
        ]
        ordering = ['number']

    participant = models.ForeignKey(Participant, on_delete=models.CASCADE)
    competition = models.ForeignKey(Competition, on_delete=models.CASCADE)
    number = models.PositiveIntegerField()
    registration_date = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.participant.name} - {self.competition.name} #{self.number}"
