from decimal import Decimal

from django.db import migrations
from django.db.models import Avg


def recalculate_competition_results(apps, schema_editor):
    Round = apps.get_model('competitions', 'Round')
    Score = apps.get_model('scoring', 'Score')
    CompetitionResult = apps.get_model('scoring', 'CompetitionResult')

    for round_obj in Round.objects.all():
        participant_ids = list(
            Score.objects.filter(
                criterion__round=round_obj,
                status='SUBMITTED',
            ).values_list('participant_id', flat=True).distinct()
        )

        totals = []
        for participant_id in participant_ids:
            criterion_averages = Score.objects.filter(
                participant_id=participant_id,
                criterion__round=round_obj,
                status='SUBMITTED',
            ).values('criterion_id').annotate(average=Avg('score'))
            total = sum(
                (row['average'] for row in criterion_averages),
                Decimal('0'),
            ).quantize(Decimal('0.01'))
            totals.append((participant_id, total))

        totals.sort(key=lambda item: item[1], reverse=True)
        previous_total = None
        current_rank = 1
        for index, (participant_id, total) in enumerate(totals, start=1):
            if previous_total is not None and total != previous_total:
                current_rank = index
            CompetitionResult.objects.update_or_create(
                competition_id=round_obj.competition_id,
                participant_id=participant_id,
                round_id=round_obj.id,
                defaults={
                    'total_score': total,
                    'rank': current_rank,
                },
            )
            previous_total = total


class Migration(migrations.Migration):
    dependencies = [
        ('scoring', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(
            recalculate_competition_results,
            reverse_code=migrations.RunPython.noop,
        ),
    ]
