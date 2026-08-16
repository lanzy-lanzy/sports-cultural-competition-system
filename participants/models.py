from django.db import models
from competitions.models import Competition


class Participant(models.Model):
    class Meta:
        db_table = 'competition_app_participant'

    competitions = models.ManyToManyField(Competition, related_name='participants', through='ParticipantCompetition')
    name = models.CharField(max_length=200)
    profile_image = models.ImageField(upload_to='participant_profiles/', null=True, blank=True)
    email = models.EmailField(unique=True)
    phone = models.CharField(max_length=20)
    age = models.PositiveIntegerField(null=True, blank=True)
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

    def __str__(self):
        return self.name

    def clean_gender(self):
        if self.gender not in ['male', 'female', 'other', 'prefer_not_to_say']:
            raise ValueError("Invalid gender")


class ParticipantCompetition(models.Model):
    class Meta:
        db_table = 'competition_app_participantcompetition'
        unique_together = ['competition', 'number']
        ordering = ['number']

    participant = models.ForeignKey(Participant, on_delete=models.CASCADE)
    competition = models.ForeignKey(Competition, on_delete=models.CASCADE)
    number = models.PositiveIntegerField()
    registration_date = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.participant.name} - {self.competition.name} #{self.number}"
