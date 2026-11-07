from decimal import Decimal
from collections import OrderedDict
from django.db import transaction

from participants.models import Participant
from competitions.models import Competition
from teams.models import TeamMembership
from .models import Award, AwardRecipient, Score, CompetitionResult, ScoreChangeLog


MEDAL_POINTS = {
    Award.Type.GOLD_MEDAL: Decimal('10'),
    Award.Type.SILVER_MEDAL: Decimal('5'),
    Award.Type.BRONZE_MEDAL: Decimal('3'),
}

# Score statuses that count toward official totals and rankings.
COUNTED_STATUSES = ('SUBMITTED', 'VERIFIED')


def medal_points_for(competition):
    """Per-competition gold/silver/bronze point values, falling back to defaults."""
    if competition is None:
        return dict(MEDAL_POINTS)
    return {
        Award.Type.GOLD_MEDAL: Decimal(str(competition.gold_points)),
        Award.Type.SILVER_MEDAL: Decimal(str(competition.silver_points)),
        Award.Type.BRONZE_MEDAL: Decimal(str(competition.bronze_points)),
    }

# Maps the podium labels produced by sports.services.event_podium onto award types.
SPORT_MEDAL_TO_AWARD = {
    'gold': Award.Type.GOLD_MEDAL,
    'silver': Award.Type.SILVER_MEDAL,
    'bronze': Award.Type.BRONZE_MEDAL,
}

PODIUM_ORDER = ('gold', 'silver', 'bronze')


def record_score_change(score, action, user=None, old_score=None, old_status='', details=''):
    """Append an immutable history row for a score creation or mutation."""
    ScoreChangeLog.objects.create(
        score=score,
        participant_id=score.participant_id,
        criterion_id=score.criterion_id,
        judge_id=score.judge_id,
        competition_id=score.criterion.round.competition_id,
        round_id=score.criterion.round_id,
        action=action,
        old_score=old_score,
        new_score=score.score,
        old_status=old_status,
        new_status=score.status,
        changed_by=user if (user is not None and user.is_authenticated) else None,
        details=details[:255],
    )


def contestant_identity(team=None, participant=None):
    """Group a medal under a delegation.

    Returns ``(key, name)`` so that the same delegation always produces the same
    key regardless of whether the medal came from an award or a match result.
    Teams win outright; individuals are folded into their active team, then
    their named delegation, and only stand alone when they have neither.
    """
    if team is not None:
        return ('team', team.id), team.name
    if participant is None:
        return None, 'TBD'

    membership = getattr(participant, 'team_membership', None)
    if membership is not None and membership.status == TeamMembership.Status.ACTIVE:
        return ('team', membership.team_id), membership.team.name
    if participant.team_name:
        return ('delegation', participant.team_name.strip().lower()), participant.team_name
    return ('individual', participant.id), participant.name


def _award_medals(competition):
    """Yield ``(key, name, medal_type, source, points, participant, provisional)`` for a competition's awards."""
    points_map = medal_points_for(competition)
    recipients = (
        AwardRecipient.objects
        .filter(award__competition=competition, award__is_active=True)
        .select_related(
            'award', 'team', 'participant', 'participant__team_membership',
            'participant__team_membership__team',
        )
        .order_by('award__type', 'id')
    )
    for recipient in recipients:
        atype = recipient.award.type
        if atype not in points_map:
            continue
        key, name = contestant_identity(
            team=recipient.team, participant=recipient.participant,
        )
        # Manual awards are entered deliberately, so they count as final.
        yield key, name, atype, 'award', points_map[atype], recipient.participant, False


def _sports_medals(competition):
    """Yield sport-event podiums; every match of the event must be decided.

    The event-level podium is final once its bracket is fully played, even if
    the wider competition is still running, so these medals are never marked
    provisional.
    """
    from sports.services import event_podium

    points_map = medal_points_for(competition)
    for event in competition.sport_events.all():
        for entry, medal in event_podium(event):
            atype = SPORT_MEDAL_TO_AWARD.get(medal)
            if atype is None:
                continue
            key, name = contestant_identity(team=entry.team, participant=entry.participant)
            yield key, name, atype, 'sports', points_map[atype], entry.participant, False


def _has_manual_medal_awards(competition):
    return competition.awards.filter(
        is_active=True, type__in=MEDAL_POINTS,
    ).exists()


def _standings_medals(competition):
    """Yield podium medals for a judged competition from its standings.

    Manual awards always win: this only fills the gap for a judged
    competition that has no medal awards entered yet. A COMPLETED
    competition's podium is final. An ACTIVE (still running) competition
    contributes provisional medals derived from the rounds that already
    carry standings, so Socio Cultural events appear on the tally and the
    bar graphs while the competition is ongoing instead of vanishing from
    it. Only participants who have actually been judged can reach the
    podium, and DRAFT or CANCELLED competitions contribute nothing.
    """
    if competition.status not in ('ACTIVE', 'COMPLETED'):
        return
    if _has_manual_medal_awards(competition):
        return
    if not competition.rounds.exists():
        return

    points_map = medal_points_for(competition)
    provisional = competition.status != 'COMPLETED'
    standings = build_overall_standings(competition)
    if provisional:
        # Rank only judged participants; an unscored zero must not place
        # anybody on a podium that has not been performed yet.
        scored = set(
            CompetitionResult.objects.filter(
                round__competition=competition,
            ).values_list('participant_id', flat=True).distinct()
        )
        standings = OrderedDict(
            (pid, data) for pid, data in standings.items() if pid in scored
        )
        if not standings:
            return
    participants = {
        p.id: p
        for p in competition.participants.select_related('team_membership__team')
    }
    ranked = sorted(standings.items(), key=lambda item: item[1]['rank'])

    for medal, position in zip(PODIUM_ORDER, (1, 2, 3)):
        for participant_id, data in ranked:
            if data['rank'] != position:
                continue
            participant = participants.get(participant_id)
            if participant is None:
                continue
            key, name = contestant_identity(participant=participant)
            yield key, name, SPORT_MEDAL_TO_AWARD[medal], 'standings', points_map[SPORT_MEDAL_TO_AWARD[medal]], participant, provisional
            break


def _rank_rows(tally):
    """Sort medal counts into rows, awarding shared ranks for identical totals."""
    rows = sorted(
        tally.values(),
        key=lambda row: (
            -row['points'], -row['gold'], -row['silver'], -row['bronze'], row['name'].lower(),
        ),
    )
    rank = 0
    previous_key = None
    for idx, row in enumerate(rows, start=1):
        key = (row['points'], row['gold'], row['silver'], row['bronze'])
        if previous_key is not None and key == previous_key:
            row['rank'] = rank
        else:
            rank = idx
            row['rank'] = rank
        previous_key = key
    return rows


def _accumulate(medals, track_sources=False):
    """Fold medal tuples into ranked tally rows.

    Each tuple is ``(key, name, medal_type, source, points, participant,
    provisional)``. A row is flagged ``provisional`` when any of its medals
    came from a competition that is still running.
    """
    tally = {}
    for key, name, atype, source, points, _recipient, provisional in medals:
        row = tally.setdefault(key, {
            'key': key,
            'name': name,
            'gold': 0,
            'silver': 0,
            'bronze': 0,
            'points': Decimal('0'),
            'provisional': False,
        })
        if atype == Award.Type.GOLD_MEDAL:
            row['gold'] += 1
        elif atype == Award.Type.SILVER_MEDAL:
            row['silver'] += 1
        elif atype == Award.Type.BRONZE_MEDAL:
            row['bronze'] += 1
        row['points'] += points
        row['provisional'] = row['provisional'] or provisional
        if track_sources:
            row.setdefault('sources', {})
            row['sources'][source] = row['sources'].get(source, 0) + 1

    rows = _rank_rows(tally)
    if track_sources:
        for row in rows:
            sources = row.get('sources', {})
            row['sports'] = sources.get('sports', 0)
            row['award'] = sources.get('award', 0)
            row['standings'] = sources.get('standings', 0)
    return rows


def _accumulate_individuals(medals):
    """Fold medals per named participant, ignoring team and delegation folding.

    The main tally merges individual medals into their delegation; the bar
    graph also needs to credit the person themselves, so every medal earned
    directly by a participant counts against that participant here.
    """
    tally = {}
    for _key, _name, atype, _source, points, recipient, provisional in medals:
        if recipient is None:
            continue
        row = tally.setdefault(recipient.id, {
            'key': ('individual', recipient.id),
            'name': recipient.name,
            'gold': 0,
            'silver': 0,
            'bronze': 0,
            'points': Decimal('0'),
            'provisional': False,
        })
        if atype == Award.Type.GOLD_MEDAL:
            row['gold'] += 1
        elif atype == Award.Type.SILVER_MEDAL:
            row['silver'] += 1
        elif atype == Award.Type.BRONZE_MEDAL:
            row['bronze'] += 1
        row['points'] += points
        row['provisional'] = row['provisional'] or provisional
    return _rank_rows(tally)


def _chart_series(rows):
    """Convert tally rows into JSON-safe data for the vendored Chart.js graph.

    Decimal points and Python bools are flattened so the list can be embedded
    straight into the page with ``json_script``.
    """
    return [
        {
            'name': row['name'],
            'rank': row['rank'],
            'gold': row['gold'],
            'silver': row['silver'],
            'bronze': row['bronze'],
            'total': row['total_medals'],
            'points': float(row['points']),
            'provisional': bool(row['provisional']),
        }
        for row in rows
    ]


def _team_records(competition=None):
    """Win/loss/draw counts per team from completed matches.

    Scoped to one competition when given, otherwise every match across the
    system counts, so per-competition and overall tallies each see their own
    record. Returns ``{team_id: {'wins', 'losses', 'draws'}}``.
    """
    from django.db.models import Count
    from sports.models import Match, MatchEntry

    completed = MatchEntry.objects.filter(
        team__isnull=False,
        match__status=Match.Status.COMPLETED,
    )
    if competition is not None:
        completed = completed.filter(match__event__competition=competition)

    records = {}
    for outcome, queryset in (
        ('wins', completed.filter(is_winner=True)),
        ('draws', completed.filter(is_draw=True)),
        ('losses', completed.filter(is_winner=False, is_draw=False)),
    ):
        for counts in queryset.values('team_id').annotate(total=Count('id')):
            record = records.setdefault(counts['team_id'], {'wins': 0, 'losses': 0, 'draws': 0})
            record[outcome] = counts['total']
    return records


def attach_team_records(rows, competition=None):
    """Enrich tally rows with each registered team's status and match record.

    Team rows gain ``status``/``status_display`` (the team's registration
    status) plus ``wins``, ``losses``, ``draws``, ``played`` and ``win_pct``
    from completed matches, so the medal table doubles as a standings board.
    Delegation and individual rows get neutral values the templates render
    as a dash. Ranking stays on the existing ``rank`` field, which already
    reflects each delegation's current position on the tally.
    """
    from teams.models import Team

    if not rows:
        return

    records = _team_records(competition)
    team_ids = {
        row['key'][1] for row in rows
        if isinstance(row.get('key'), tuple) and row['key'][0] == 'team'
    }
    statuses = dict(Team.objects.filter(id__in=team_ids).values_list('id', 'status'))
    status_labels = dict(Team.Status.choices)

    for row in rows:
        key = row.get('key')
        if not (isinstance(key, tuple) and key[0] == 'team'):
            row.update({
                'status': '', 'status_display': '',
                'wins': 0, 'losses': 0, 'draws': 0, 'played': 0, 'win_pct': None,
            })
            continue
        record = records.get(key[1], {'wins': 0, 'losses': 0, 'draws': 0})
        played = record['wins'] + record['losses'] + record['draws']
        status = statuses.get(key[1], '')
        row.update({
            'status': status,
            'status_display': status_labels.get(status, ''),
            'wins': record['wins'],
            'losses': record['losses'],
            'draws': record['draws'],
            'played': played,
            'win_pct': (record['wins'] / played) if played else None,
        })


def compute_medal_tally(competition):
    """Aggregate medals per team or delegation for one competition.

    Combines manually assigned awards with medals derived from the competition's
    sport events, so a sports meet reports a podium without anyone entering it by
    hand. Returns ``{'rows': [...], 'champion': row_or_None}`` where each row has
    rank, name, medal counts, and points (gold/silver/bronze values are
    configurable per competition on the Competition model).
    """
    medals = (
        list(_award_medals(competition))
        + list(_sports_medals(competition))
        + list(_standings_medals(competition))
    )
    rows = _accumulate(medals)
    attach_team_records(rows, competition)
    individuals = _accumulate_individuals(medals)
    team_rows = [
        row for row in rows
        if isinstance(row.get('key'), tuple) and row['key'][0] in ('team', 'delegation')
    ]

    for row in rows + individuals:
        row['total_medals'] = row['gold'] + row['silver'] + row['bronze']
    chart_max_medals = max(
        (row['total_medals'] for row in rows + individuals), default=0,
    )
    return {
        'rows': rows,
        'champion': rows[0] if rows else None,
        'team_rows': team_rows,
        'individuals': individuals,
        'chart_max_medals': chart_max_medals,
        'team_chart': _chart_series(team_rows),
        'individual_chart': _chart_series(individuals),
    }


def compute_overall_medal_tally(competitions=None):
    """Aggregate medals across competitions into one system-wide tally.

    Every competition is merged so the same delegation accumulates medals from
    sport events and from judged competitions alike. Returns the ranked rows,
    the champion, and a per-competition breakdown of what each one contributed.
    """
    if competitions is None:
        queryset = Competition.objects.all().select_related().prefetch_related('sport_events')
    elif hasattr(competitions, 'select_related'):
        queryset = competitions.select_related().prefetch_related('sport_events')
    else:
        queryset = list(competitions)

    medals = []
    breakdown = []
    for competition in queryset:
        competition_medals = (
            list(_award_medals(competition))
            + list(_sports_medals(competition))
            + list(_standings_medals(competition))
        )
        medals.extend(competition_medals)
        rows = _accumulate(competition_medals, track_sources=True)
        attach_team_records(rows, competition)
        breakdown.append({
            'competition': competition,
            'rows': rows,
            'champion': rows[0] if rows else None,
            'medal_count': len(competition_medals),
        })

    rows = _accumulate(medals, track_sources=True)
    attach_team_records(rows)
    individuals = _accumulate_individuals(medals)
    team_rows = [
        row for row in rows
        if isinstance(row.get('key'), tuple) and row['key'][0] in ('team', 'delegation')
    ]

    # Shared scale so team and individual bars can be compared side by side.
    for row in rows + individuals:
        row['total_medals'] = row['gold'] + row['silver'] + row['bronze']
    chart_max_medals = max(
        (row['total_medals'] for row in rows + individuals), default=0,
    )

    totals = {
        'gold': sum(row['gold'] for row in rows),
        'silver': sum(row['silver'] for row in rows),
        'bronze': sum(row['bronze'] for row in rows),
        'sports': sum(row['sports'] for row in rows),
        'award': sum(row['award'] for row in rows),
        'standings': sum(row['standings'] for row in rows),
    }
    return {
        'rows': rows,
        'champion': rows[0] if rows else None,
        'breakdown': breakdown,
        'totals': totals,
        # Bar graph series: delegation/team rows vs raw per-participant rows.
        'team_rows': team_rows,
        'individuals': individuals,
        'chart_max_medals': chart_max_medals,
        # JSON-safe payloads rendered into the page for the Chart.js graph.
        'team_chart': _chart_series(team_rows),
        'individual_chart': _chart_series(individuals),
    }


def calculate_participant_total_score(
    participant,
    round_obj,
    include_draft=True,
    judge=None,
):
    """Return the round points earned by a participant.

    Each criterion's scores are averaged across judges. When no criterion in
    the round defines a percentage weight, the criterion averages are summed
    (``max_score`` is already the criterion's point allocation). When any
    criterion carries a ``weight_percentage`` (e.g. Creativity 30%), totals
    are the weighted sum: ``average * weight / 100`` per criterion.
    """
    total_score = Decimal('0')
    criteria = list(round_obj.criteria.all())
    weighted = any(
        criterion.weight_percentage and criterion.weight_percentage > 0
        for criterion in criteria
    )

    for criterion in criteria:
        scores_query = Score.objects.filter(
            participant=participant,
            criterion=criterion
        )

        if judge is not None:
            scores_query = scores_query.filter(judge=judge)

        if include_draft:
            scores_query = scores_query.filter(
                status__in=('DRAFT',) + COUNTED_STATUSES
            )
        else:
            scores_query = scores_query.filter(status__in=COUNTED_STATUSES)

        scores = list(scores_query.values_list('score', flat=True))
        if scores:
            average = sum(scores, Decimal('0')) / Decimal(len(scores))
            if weighted:
                average *= (criterion.weight_percentage or Decimal('0')) / Decimal('100')
            total_score += average

    return total_score.quantize(Decimal('0.01'))


def calculate_rankings(round_obj):
    """Calculate and update rankings for a round."""
    with transaction.atomic():
        participants = Participant.objects.filter(
            scores__criterion__round=round_obj,
            scores__status__in=COUNTED_STATUSES
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
                status__in=COUNTED_STATUSES
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
