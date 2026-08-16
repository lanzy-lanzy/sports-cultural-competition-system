from django.db import models
from django.contrib.auth.models import User


class Competition(models.Model):
    class Meta:
        db_table = 'competition_app_competition'

    name = models.CharField(max_length=200)
    description = models.TextField()
    start_date = models.DateTimeField()
    end_date = models.DateTimeField()
    status = models.CharField(max_length=20, choices=[
        ('DRAFT', 'Draft'),
        ('ACTIVE', 'Active'),
        ('COMPLETED', 'Completed'),
        ('CANCELLED', 'Cancelled')
    ], default='DRAFT')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(User, on_delete=models.PROTECT, related_name='competitions_created')
    show_results = models.BooleanField(default=False)

    def __str__(self):
        return self.name


class Round(models.Model):
    class Meta:
        db_table = 'competition_app_round'
        ordering = ['order']

    competition = models.ForeignKey(Competition, on_delete=models.CASCADE, related_name='rounds')
    name = models.CharField(max_length=200)
    description = models.TextField()
    order = models.PositiveIntegerField()
    status = models.CharField(max_length=20, choices=[
        ('PENDING', 'Pending'),
        ('ONGOING', 'Ongoing'),
        ('COMPLETED', 'Completed')
    ], default='PENDING')
    weight_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=0)

    def __str__(self):
        return self.name


class Criterion(models.Model):
    class Meta:
        db_table = 'competition_app_criterion'

    round = models.ForeignKey(Round, on_delete=models.CASCADE, related_name='criteria')
    name = models.CharField(max_length=200)
    description = models.TextField()
    max_score = models.DecimalField(max_digits=5, decimal_places=2)
