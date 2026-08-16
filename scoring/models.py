from django.db import models
from participants.models import Participant
from competitions.models import Competition, Criterion, Round
from judges.models import Judge


class Score(models.Model):
    class Meta:
        db_table = 'competition_app_score'
        unique_together = ['participant', 'criterion', 'judge']

    participant = models.ForeignKey(Participant, on_delete=models.CASCADE, related_name='scores')
    criterion = models.ForeignKey(Criterion, on_delete=models.CASCADE, related_name='scores')
    judge = models.ForeignKey(Judge, on_delete=models.CASCADE, related_name='scores')
    score = models.DecimalField(max_digits=5, decimal_places=2)
    remarks = models.TextField(blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=[
        ('DRAFT', 'Draft'),
        ('SUBMITTED', 'Submitted'),
        ('VERIFIED', 'Verified')
    ], default='DRAFT')

    def __str__(self):
        return f"{self.participant} - {self.criterion} - {self.judge}"


class CompetitionResult(models.Model):
    class Meta:
        db_table = 'competition_app_competitionresult'
        unique_together = ['competition', 'participant', 'round']

    competition = models.ForeignKey(Competition, on_delete=models.CASCADE, related_name='results')
    participant = models.ForeignKey(Participant, on_delete=models.CASCADE, related_name='results')
    round = models.ForeignKey(Round, on_delete=models.CASCADE, related_name='results')
    total_score = models.DecimalField(max_digits=10, decimal_places=2)
    rank = models.PositiveIntegerField()
    timestamp = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.participant} - {self.competition} - {self.round}"
