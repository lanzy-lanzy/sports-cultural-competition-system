from decimal import Decimal

from django.db import models
from django.contrib.auth.models import User


class Competition(models.Model):
    class Kind(models.TextChoices):
        SPORTS = 'SPORTS', 'Sports competition'
        CULTURAL = 'CULTURAL', 'Cultural competition'
        MIXED = 'MIXED', 'Mixed / other'

    class CulturalEventType(models.TextChoices):
        DANCE = 'DANCE', 'Dance Competition'
        SINGING = 'SINGING', 'Singing Competition'
        CULTURAL_PRESENTATION = 'CULTURAL_PRESENTATION', 'Cultural Presentation'
        ESSAY_WRITING = 'ESSAY_WRITING', 'Essay Writing'
        POSTER_MAKING = 'POSTER_MAKING', 'Poster Making'
        QUIZ_BEE = 'QUIZ_BEE', 'Quiz Bee'
        SPOKEN_POETRY = 'SPOKEN_POETRY', 'Spoken Poetry'
        COSTUME = 'COSTUME', 'Costume Competition'
        TALENT_SHOW = 'TALENT_SHOW', 'Talent Show'
        OTHER = 'OTHER', 'Other cultural event'

    class Meta:
        db_table = 'competition_app_competition'

    name = models.CharField(max_length=200)
    description = models.TextField()
    kind = models.CharField(
        max_length=20,
        choices=Kind.choices,
        default=Kind.MIXED,
        help_text='What kind of competition this is.',
    )
    cultural_event_type = models.CharField(
        max_length=30,
        choices=CulturalEventType.choices,
        blank=True,
        default='',
        help_text='Only used for cultural competitions.',
    )
    gold_points = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal('10'),
        help_text='Points per gold medal in the medal tally.',
    )
    silver_points = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal('5'),
        help_text='Points per silver medal in the medal tally.',
    )
    bronze_points = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal('3'),
        help_text='Points per bronze medal in the medal tally.',
    )
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
    weight_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('0'),
        help_text=(
            'Optional percentage weight (e.g. 30 for 30%). When any criterion in '
            'the round uses weights, totals are computed as the weighted sum of '
            'criterion scores; otherwise criterion averages are summed directly.'
        ),
    )

    def __str__(self):
        return self.name
