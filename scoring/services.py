from decimal import Decimal
from collections import OrderedDict
from django.db import transaction

from participants.models import Participant
from .models import Score, CompetitionResult


def calculate_participant_total_score(
    participant,
    round_obj,
    include_draft=True,
    judge=None,
):
    """Return the round points earned by a participant.

    Each criterion's scores are averaged across judges, then the criterion
    point averages are summed. ``max_score`` is already the criterion's point
    allocation, so applying it as a percentage would scale the points twice.
    """
    total_score = Decimal('0')
    criteria = round_obj.criteria.all()

    for criterion in criteria:
        scores_query = Score.objects.filter(
            participant=participant,
            criterion=criterion
        )

        if judge is not None:
            scores_query = scores_query.filter(judge=judge)

        if include_draft:
            scores_query = scores_query.filter(status__in=['DRAFT', 'SUBMITTED'])
        else:
            scores_query = scores_query.filter(status='SUBMITTED')

        scores = list(scores_query.values_list('score', flat=True))
        if scores:
            total_score += sum(scores, Decimal('0')) / Decimal(len(scores))

    return total_score.quantize(Decimal('0.01'))


def calculate_rankings(round_obj):
    """Calculate and update rankings for a round."""
    with transaction.atomic():
        participants = Participant.objects.filter(
            scores__criterion__round=round_obj,
            scores__status='SUBMITTED'
        ).distinct()

        results = []
        for participant in participants:
            total_score = calculate_participant_total_score(participant, round_obj, include_draft=False)
            results.append({
                'participant': participant,
                'total_score': total_score
            })

        results.sort(key=lambda x: x['total_score'], reverse=True)

        current_rank = 1
        previous_score = None
        rank_count = 0

        for result in results:
            if previous_score != result['total_score']:
                current_rank = rank_count + 1

            CompetitionResult.objects.update_or_create(
                competition=round_obj.competition,
                participant=result['participant'],
                round=round_obj,
                defaults={
                    'total_score': result['total_score'],
                    'rank': current_rank
                }
            )

            previous_score = result['total_score']
            rank_count += 1


def build_round_results(competition):
    """Build per-round participant score details (podium + tables) for a competition."""
    for round_obj in competition.rounds.all():
        scores_list = []
        for participant in competition.participants.all():
            total_score = calculate_participant_total_score(participant, round_obj, include_draft=False)

            scores = Score.objects.filter(
                participant=participant,
                criterion__round=round_obj,
                status='SUBMITTED'
            ).select_related('criterion', 'judge', 'judge__user')

            criterion_scores = {}
            judge_scores = {}

            for score in scores:
                judge_id = score.judge.id
                if judge_id not in judge_scores:
                    judge_scores[judge_id] = {
                        'judge_name': score.judge.user.get_full_name() or score.judge.user.username,
                        'scores': {}
                    }
                judge_scores[judge_id]['scores'][score.criterion_id] = score.score

                if score.criterion_id not in criterion_scores:
                    criterion_scores[score.criterion_id] = Decimal('0')
                criterion_scores[score.criterion_id] += Decimal(str(score.score))

            num_judges = len(judge_scores)
            if num_judges > 0:
                for criterion_id in criterion_scores:
                    criterion_scores[criterion_id] /= Decimal(str(num_judges))

            scores_list.append({
                'participant_id': participant.id,
                'total_score': total_score,
                'criterion_scores': criterion_scores,
                'judge_scores': judge_scores
            })

        scores_list.sort(key=lambda x: x['total_score'], reverse=True)

        round_obj.participant_scores = OrderedDict()
        current_rank = 1
        previous_score = None
        for i, score_data in enumerate(scores_list):
            if previous_score is not None and score_data['total_score'] != previous_score:
                current_rank = i + 1

            round_obj.participant_scores[score_data['participant_id']] = {
                'total': score_data['total_score'],
                'scores': score_data['criterion_scores'],
                'judge_scores': score_data['judge_scores'],
                'rank': current_rank
            }
            previous_score = score_data['total_score']

    return competition.rounds.all()


def build_overall_standings(competition):
    """Compute weighted final standings across all rounds for a competition."""
    standings = {}
    for participant in competition.participants.all():
        total = Decimal('0')
        for round_obj in competition.rounds.all():
            result = CompetitionResult.objects.filter(
                round=round_obj,
                participant=participant
            ).first()
            if result:
                total += result.total_score * (round_obj.weight_percentage / Decimal('100'))
        standings[participant.id] = {
            'total': Decimal(str(total)).quantize(Decimal('0.01')),
        }

    ranked = sorted(standings.items(), key=lambda x: x[1]['total'], reverse=True)

    ordered = OrderedDict()
    current_rank = 1
    previous_score = None
    for i, (participant_id, data) in enumerate(ranked):
        if previous_score is not None and data['total'] != previous_score:
            current_rank = i + 1
        data['rank'] = current_rank
        ordered[participant_id] = data
        previous_score = data['total']

    return ordered
