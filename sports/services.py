import math
from decimal import Decimal
from collections import OrderedDict

from django.db import transaction
from django.db.models import Max

from .models import Match, MatchEntry, SportsEvent


def _seed_order(size):
    """Return the standard single-elimination bracket seeding order for a power-of-two size."""
    slots = [1]
    for r in range(int(math.log2(size))):
        slots = [s for slot in slots for s in (slot, 2 ** (r + 1) + 1 - slot)]
    return slots


def _place_entry(match, entry, side):
    """Create or refresh a MatchEntry on ``side`` of ``match``."""
    if match is None or entry is None:
        return
    MatchEntry.objects.update_or_create(
        match=match,
        side=side,
        defaults={
            'team': entry.team,
            'participant': entry.participant,
        },
    )


def _advance_winner(match, entry):
    """Place the winner of ``match`` into its ``next_match`` on the correct side."""
    if not match.next_match_id:
        return
    target = match.next_match
    peers = list(Match.objects.filter(event=match.event, round_number=match.round_number).order_by('id'))
    try:
        idx = peers.index(match)
    except ValueError:
        return
    side = (idx % 2) + 1
    _place_entry(target, entry, side)


def _build_elimination_matches(event, entries=None, start_round=1):
    """Build a single-elimination bracket. ``entries`` defaults to confirmed entries.

    ``start_round`` offsets the round numbers (used for knockout stages that follow
    a group stage, which already occupies round 1).
    """
    if entries is None:
        entries = list(event.entries.filter(status='CONFIRMED').order_by('seed', 'id'))
    n = len(entries)
    if n < 2:
        return []
    rounds = math.ceil(math.log2(n))
    size = 2 ** rounds
    order = _seed_order(size)
    seed_map = {i + 1: entry for i, entry in enumerate(entries)}

    matches_by_round = []
    for r in range(rounds):
        count = size // (2 ** (r + 1))
        round_matches = [
            Match.objects.create(
                event=event,
                name=f'Round {start_round + r}',
                round_number=start_round + r,
            )
            for _ in range(count)
        ]
        matches_by_round.append(round_matches)

    for r in range(rounds - 1):
        for i, match in enumerate(matches_by_round[r]):
            match.next_match = matches_by_round[r + 1][i // 2]
            match.save(update_fields=['next_match'])

    slot_idx = 0
    for match in matches_by_round[0]:
        seed_a = order[slot_idx]
        seed_b = order[slot_idx + 1]
        slot_idx += 2
        entry_a = seed_map.get(seed_a)
        entry_b = seed_map.get(seed_b)

        if entry_a is not None:
            MatchEntry.objects.create(
                match=match,
                team=entry_a.team,
                participant=entry_a.participant,
                side=1,
            )
        if entry_b is not None:
            MatchEntry.objects.create(
                match=match,
                team=entry_b.team,
                participant=entry_b.participant,
                side=2,
            )

        # Bye: single confirmed entry advances automatically.
        sole = entry_a if entry_b is None else entry_b if entry_a is None else None
        if sole is not None:
            match_entry = match.entries.get(side=1 if sole is entry_a else 2)
            match_entry.is_winner = True
            match_entry.save(update_fields=['is_winner'])
            match.status = Match.Status.COMPLETED
            match.save(update_fields=['status', 'updated_at'])
            _advance_winner(match, match_entry)

    return matches_by_round


def _generate_round_robin(event, group=None):
    entries = list(event.entries.filter(status='CONFIRMED').order_by('seed', 'id'))
    n = len(entries)
    if n < 2:
        return
    teams = list(entries)
    if n % 2 == 1:
        teams.append(None)

    rounds_pairs = []
    for _ in range(len(teams) - 1):
        pairs = []
        for i in range(len(teams) // 2):
            pairs.append((teams[i], teams[len(teams) - 1 - i]))
        rounds_pairs.append(pairs)
        teams = [teams[0]] + [teams[-1]] + teams[1:-1]

    rounds_pairs = rounds_pairs * event.cycles
    match_num = 1
    for round_number, pairs in enumerate(rounds_pairs, start=1):
        for entry_a, entry_b in pairs:
            if entry_a is None or entry_b is None:
                continue
            match = Match.objects.create(
                event=event,
                name=f'Match {match_num}',
                round_number=round_number,
                group=group,
            )
            MatchEntry.objects.create(match=match, team=entry_a.team, participant=entry_a.participant, side=1)
            MatchEntry.objects.create(match=match, team=entry_b.team, participant=entry_b.participant, side=2)
            match_num += 1


def _generate_group_stage(event):
    """Split confirmed entries into balanced groups and run round-robin within each group."""
    entries = list(event.entries.filter(status='CONFIRMED').order_by('seed', 'id'))
    n = len(entries)
    if n < 2:
        return

    group_count = event.group_count
    if group_count < 1 or n // group_count < max(2, event.qualifiers_per_group):
        raise ValueError('Each group needs at least two entries and enough entries for the configured qualifiers.')

    groups = [[] for _ in range(group_count)]
    for idx, entry in enumerate(entries):
        groups[idx % group_count].append(entry)

    names = [chr(ord('A') + g) for g in range(group_count)]
    for group_name, members in zip(names, groups):
        team_list = list(members)
        if len(team_list) % 2 == 1:
            team_list.append(None)

        pairs_rounds = []
        for _ in range(len(team_list) - 1):
            pairs = []
            for i in range(len(team_list) // 2):
                pairs.append((team_list[i], team_list[len(team_list) - 1 - i]))
            pairs_rounds.append(pairs)
            team_list = [team_list[0]] + [team_list[-1]] + team_list[1:-1]

        match_num = 1
        for round_number, pairs in enumerate(pairs_rounds * event.cycles, start=1):
            for entry_a, entry_b in pairs:
                if entry_a is None or entry_b is None:
                    continue
                match = Match.objects.create(
                    event=event,
                    name=f'Group {group_name} - Match {match_num}',
                    round_number=1,
                    group=group_name,
                )
                MatchEntry.objects.create(match=match, team=entry_a.team, participant=entry_a.participant, side=1)
                MatchEntry.objects.create(match=match, team=entry_b.team, participant=entry_b.participant, side=2)
                match_num += 1


def _generate_double_elimination(event):
    """Build a winners/losers bracket plus a grand final.

    Pads the draw to the next power of two and advances empty feeder paths as byes.
    """
    entries = list(event.entries.filter(status='CONFIRMED').order_by('seed', 'id'))
    n = len(entries)
    if n < 2:
        return []
    size = 2 ** math.ceil(math.log2(n))
    k = int(math.log2(size))
    order = _seed_order(size)
    seed_map = {i + 1: entry for i, entry in enumerate(entries)}

    # Winners bracket.
    wb = []
    for r in range(k):
        count = size // (2 ** (r + 1))
        round_matches = [
            Match.objects.create(event=event, name=f'WB Round {r + 1}', round_number=r + 1)
            for _ in range(count)
        ]
        wb.append(round_matches)
    for r in range(k - 1):
        for i, match in enumerate(wb[r]):
            match.next_match = wb[r + 1][i // 2]
            match.save(update_fields=['next_match'])

    # Losers bracket.
    lb_rounds = max(0, 2 * k - 2)
    lb = []
    for l in range(lb_rounds):
        count = size // (2 ** ((l + 2) // 2 + 1))
        round_matches = [
            Match.objects.create(event=event, name=f'LB Round {l + 1}', round_number=k + l + 1)
            for _ in range(count)
        ]
        lb.append(round_matches)

    grand = Match.objects.create(event=event, name='Grand Final', round_number=3 * k - 1)
    wb[k - 1][0].next_match = grand
    wb[k - 1][0].save(update_fields=['next_match'])

    for l in range(lb_rounds):
        for i, match in enumerate(lb[l]):
            if l == lb_rounds - 1:
                match.next_match = grand
            elif l % 2 == 0:
                match.next_match = lb[l + 1][i]
            else:
                match.next_match = lb[l + 1][i // 2]
            match.save(update_fields=['next_match'])

    # Seed the first winners round.
    slot_idx = 0
    for match in wb[0]:
        seed_a = order[slot_idx]
        seed_b = order[slot_idx + 1]
        slot_idx += 2
        entry_a = seed_map.get(seed_a)
        entry_b = seed_map.get(seed_b)
        if entry_a is not None:
            MatchEntry.objects.create(match=match, team=entry_a.team, participant=entry_a.participant, side=1)
        if entry_b is not None:
            MatchEntry.objects.create(match=match, team=entry_b.team, participant=entry_b.participant, side=2)

    return wb, lb, grand


def _double_elim_rounds(event):
    """Return (k, lb_rounds) for a double-elimination event, derived from its matches."""
    grand = event.matches.filter(name='Grand Final').first()
    if grand is None:
        return 1, 0
    k = (grand.round_number + 1) // 3
    return k, max(0, 2 * k - 2)


def _advance_double_elim(match, winner, loser, event):
    """Advance winners through the winners/losers bracket and feed losers into it."""
    k, _ = _double_elim_rounds(event)
    grand = event.matches.filter(name='Grand Final').first()
    round_no = match.round_number

    if match.name == 'Grand Final Reset':
        return
    if grand is not None and round_no == grand.round_number:
        if winner and winner.side == 2 and event.grand_final_reset:
            reset, _ = Match.objects.get_or_create(event=event, name='Grand Final Reset', defaults={'round_number': grand.round_number + 1})
            _place_entry(reset, winner, 2)
            _place_entry(reset, loser, 1)
        return

    if round_no <= k:
        # Winners bracket.
        r = round_no - 1
        if r == k - 1:
            # WB final: winner -> grand (side 1), loser -> last LB round (side 2).
            if grand is not None:
                _place_entry(grand, winner, 1)
            last_lb = event.matches.filter(round_number=3 * k - 2, name__startswith='LB Round').order_by('id').first()
            if last_lb is not None:
                _place_entry(last_lb, loser, 2)
            elif grand is not None:
                _place_entry(grand, loser, 2)
            return
        _advance_winner(match, winner)
        peers = list(Match.objects.filter(event=event, round_number=round_no).order_by('id'))
        try:
            idx = peers.index(match)
        except ValueError:
            return
        lb_round = list(event.matches.filter(round_number=k + (1 if r == 0 else 2 * r)).order_by('id'))
        if r == 0:
            lb_match = lb_round[idx // 2]
            side = (idx % 2) + 1
        else:
            if idx >= len(lb_round):
                return
            lb_match = lb_round[idx]
            side = 2
        _place_entry(lb_match, loser, side)
        return

    # Losers bracket.
    nxt = match.next_match
    if nxt is None:
        return
    l = round_no - k - 1
    peers = list(Match.objects.filter(event=event, round_number=round_no).order_by('id'))
    try:
        idx = peers.index(match)
    except ValueError:
        return
    if l % 2 == 0:
        _place_entry(nxt, winner, 1)
    elif nxt == grand:
        _place_entry(grand, winner, 2)
    else:
        _place_entry(nxt, winner, (idx % 2) + 1)


@transaction.atomic
def generate_bracket(event):
    event = SportsEvent.objects.select_for_update().get(pk=event.pk)
    if event.status in ('COMPLETED', 'CANCELLED'):
        raise ValueError('Reopen this event before generating fixtures.')
    if event.matches.exists():
        raise ValueError('A bracket has already been generated. Delete existing matches first.')
    if event.playoff_count and event.format == 'LEAGUE' and event.confirmed_count < event.playoff_count:
        raise ValueError('There are fewer entries than the playoff qualifier count.')
    if event.cycles not in (1, 2):
        raise ValueError('Use a single or double round schedule.')
    if event.max_teams and event.confirmed_count > event.max_teams:
        raise ValueError('The confirmed entries exceed the event entry cap.')
    if event.format == 'LEAGUE' and event.playoff_count not in (0, 2, 4, 8):
        raise ValueError('Choose no playoffs, or a top 2, 4 or 8 playoff.')
    if not event.can_generate_bracket():
        raise ValueError('At least two confirmed entries are required to generate a bracket.')

    if event.format in (SportsEvent.Format.SINGLE_ELIMINATION, SportsEvent.Format.KNOCKOUT):
        _build_elimination_matches(event)
    elif event.format in (SportsEvent.Format.ROUND_ROBIN, SportsEvent.Format.LEAGUE):
        _generate_round_robin(event, group='League' if event.format == 'LEAGUE' and event.playoff_count else None)
    elif event.format == SportsEvent.Format.DOUBLE_ELIMINATION:
        _generate_double_elimination(event)
        _resolve_double_byes(event)
    elif event.format == SportsEvent.Format.GROUP_STAGE:
        _generate_group_stage(event)
    elif event.format == SportsEvent.Format.BEST_OF:
        entries = list(event.entries.filter(status='CONFIRMED').order_by('seed', 'id'))
        if len(entries) != 2 or event.best_of % 2 != 1 or not 1 <= event.best_of <= 15:
            raise ValueError('Best-of Series requires exactly two entries and an odd game count from 1 to 15.')
        for game in range(1, event.best_of + 1):
            match = Match.objects.create(event=event, name=f'Game {game}', round_number=game)
            for side, entry in enumerate(entries, 1):
                _place_entry(match, entry, side)
    else:
        raise ValueError(f'Bracket generation is not supported for {event.get_format_display()}.')
    event.status = 'READY'
    event.save(update_fields=['status'])


def maybe_auto_generate_bracket(event):
    """Compatibility hook: approvals leave registration open until staff generate fixtures."""
    # Coordinators generate fixtures explicitly after registration closes.
    return False


def _entry_matches_query(event, entry, group=None, knockout_only=False):
    from django.db.models import Q

    base = event.matches.filter(status=Match.Status.COMPLETED)
    if group is not None:
        base = base.filter(group=group)
    if knockout_only:
        base = base.filter(group__isnull=True)
    if entry.team_id:
        return base.filter(entries__team_id=entry.team_id).prefetch_related('entries')
    return base.filter(entries__participant_id=entry.participant_id).prefetch_related('entries')


def _scored_opponents(match, entry):
    """Return both sides of an actual scored contest; byes are not played games."""
    sides = list(match.entries.all())
    if len(sides) != 2 or {side.side for side in sides} != {1, 2}:
        return None
    if any(side.score is None for side in sides):
        return None
    if (sides[0].team_id, sides[0].participant_id) == (sides[1].team_id, sides[1].participant_id):
        return None
    own = next((side for side in sides if (side.team_id, side.participant_id) == (entry.team_id, entry.participant_id)), None)
    if own is None:
        return None
    return own, next(side for side in sides if side.pk != own.pk)


def _round_robin_standings(event, group=None):
    rows = []
    candidates = event.entries.filter(status='CONFIRMED').select_related('team', 'participant')
    if group is not None:
        from django.db.models import Q
        matches = event.matches.filter(group=group)
        candidates = candidates.filter(Q(team_id__in=matches.values('entries__team_id')) | Q(participant_id__in=matches.values('entries__participant_id')))
    for entry in candidates:
        completed = list(_entry_matches_query(event, entry, group=group).distinct())
        played = 0
        wins = 0
        draws = 0
        losses = 0
        points_for = Decimal('0')
        points_against = Decimal('0')

        for match in completed:
            opponents = _scored_opponents(match, entry)
            if opponents is None:
                continue
            own, opponent = opponents
            played += 1
            if own.score > opponent.score:
                wins += 1
            elif own.score == opponent.score:
                draws += 1
            else:
                losses += 1
            points_for += own.score
            points_against += opponent.score

        total_points = wins * event.win_points + draws * event.draw_points + losses * event.loss_points
        point_diff = points_for - points_against
        rows.append({
            'entry': entry,
            'name': entry.display_name,
            'played': played,
            'wins': wins,
            'draws': draws,
            'losses': losses,
            'points_for': points_for,
            'points_against': points_against,
            'point_diff': point_diff,
            'total_points': total_points,
        })

    from .workflow import rank_table
    rows = rank_table(event, rows, group)

    return rows


def compute_elimination_standings(event):
    """Standings for elimination formats derived from the bracket structure.

    The champion ranks first, followed by the runner-up, then contestants ordered
    by how deep into the bracket they were eliminated.
    """
    from .workflow import final_match
    deciding = final_match(event)
    final_round = deciding.round_number if deciding else 0
    has_groups = event.matches.filter(group__isnull=False).exists()

    entries = event.entries.filter(status='CONFIRMED').select_related('team', 'participant')
    if has_groups:
        from django.db.models import Q

        knockout_teams = set(
            event.matches.filter(group__isnull=True)
            .exclude(entries__team__isnull=True)
            .values_list('entries__team', flat=True)
        )
        knockout_participants = set(
            event.matches.filter(group__isnull=True)
            .exclude(entries__participant__isnull=True)
            .values_list('entries__participant', flat=True)
        )
        entries = entries.filter(
            Q(team_id__in=knockout_teams) | Q(participant_id__in=knockout_participants)
        )

    rows = []
    for entry in entries:
        completed = list(_entry_matches_query(event, entry, knockout_only=True).distinct())
        wins = 0
        losses = 0
        last_lost_round = 0
        played = 0
        for match in completed:
            opponents = _scored_opponents(match, entry)
            if opponents is None:
                continue
            own, opponent = opponents
            played += 1
            if own.score > opponent.score:
                wins += 1
            elif own.score < opponent.score:
                losses += 1
                last_lost_round = max(last_lost_round, match.round_number)

        is_champion = False
        for match in completed:
            if not deciding or match.pk != deciding.pk:
                continue
            own = next(
                (me for me in match.entries.all()
                 if (entry.team_id and me.team_id == entry.team_id)
                 or (entry.participant_id and me.participant_id == entry.participant_id)),
                None,
            )
            if own is not None and own.is_winner:
                is_champion = True
                break

        rows.append({
            'entry': entry,
            'name': entry.display_name,
            'played': played,
            'wins': wins,
            'losses': losses,
            'last_lost_round': last_lost_round,
            'is_champion': is_champion,
            'result': 'Champion' if is_champion else 'Eliminated',
        })

    rows.sort(key=lambda row: (row['is_champion'] is False, -row['last_lost_round'], -row['wins']))
    rank = 0
    previous_key = None
    for idx, row in enumerate(rows, start=1):
        key = (row['is_champion'], row['last_lost_round'], row['wins'])
        if previous_key is not None and key == previous_key:
            row['rank'] = rank
        else:
            rank = idx
            row['rank'] = rank
        previous_key = key
    from .workflow import proposed_podium
    try:
        podium = proposed_podium(event)
    except ValueError:
        podium = []
    placement = {(e.team_id, e.participant_id): (dict(gold=1, silver=2, bronze=3)[medal], medal) for e, medal in podium}
    for row in rows:
        confirmed = placement.get((row['entry'].team_id, row['entry'].participant_id))
        if confirmed:
            row['rank'] = confirmed[0]
            row['result'] = {'gold': 'Champion', 'silver': 'Runner-up', 'bronze': 'Third place'}[confirmed[1]]
            row['is_champion'] = confirmed[1] == 'gold'
        elif podium:
            row['rank'] = max(row['rank'], len(podium) + 1)
    rows.sort(key=lambda r: r['rank'])
    return rows


def compute_standings(event):
    """Standings appropriate to the event format."""
    if (event.format == SportsEvent.Format.GROUP_STAGE or (event.format == SportsEvent.Format.LEAGUE and event.playoff_count)) and event.matches.filter(group__isnull=True).exists():
        return compute_elimination_standings(event)
    if event.format in (SportsEvent.Format.ROUND_ROBIN, SportsEvent.Format.LEAGUE, SportsEvent.Format.GROUP_STAGE, SportsEvent.Format.BEST_OF):
        return _round_robin_standings(event)
    return compute_elimination_standings(event)


def compute_team_standings(team):
    """Per-event and per-phase records; ranks from unrelated stages are never combined."""
    records = []
    events = SportsEvent.objects.filter(entries__team=team, entries__status='CONFIRMED').select_related('competition')
    for event in events:
        if event.format == SportsEvent.Format.GROUP_STAGE or (event.format == SportsEvent.Format.LEAGUE and event.playoff_count):
            groups = event.matches.filter(group__isnull=False).values_list('group', flat=True).distinct().order_by('group')
            tables = [(f'Group {group}' if event.format == SportsEvent.Format.GROUP_STAGE else 'League', compute_group_standings(event, group)) for group in groups]
            if event.matches.filter(group__isnull=True).exists():
                tables.append(('Knockout', compute_elimination_standings(event)))
            if not tables:
                tables = [('Group stage' if event.format == SportsEvent.Format.GROUP_STAGE else 'League', _round_robin_standings(event))]
        else:
            tables = [(event.get_format_display(), compute_standings(event))]
        for stage, rows in tables:
            row = next((row for row in rows if row['entry'].team_id == team.pk), None)
            if row is not None:
                records.append({'event': event, 'stage': stage, 'draws': 0, 'total_points': None, **row})
    return records


def compute_group_standings(event, group_name):
    return _round_robin_standings(event, group=group_name)


def _group_qualifiers(event):
    """Configured qualifiers from each group, ordered by group then standings."""
    groups = (
        Match.objects.filter(event=event, group__isnull=False)
        .values_list('group', flat=True)
        .distinct()
        .order_by('group')
    )
    qualifiers = []
    for group_name in groups:
        rows = compute_group_standings(event, group_name)

        if len(rows) > event.qualifiers_per_group and rows[event.qualifiers_per_group - 1]['rank'] == rows[event.qualifiers_per_group]['rank']:
            raise ValueError('Resolve the tied group qualification positions before creating the knockout stage.')
        qualifiers.extend(row['entry'] for row in rows[:event.qualifiers_per_group])
    return qualifiers


def compute_group_stage_standings(event):
    groups = []
    for group_name in (
        Match.objects.filter(event=event, group__isnull=False)
        .values_list('group', flat=True)
        .distinct()
        .order_by('group')
    ):
        rows = compute_group_standings(event, group_name)
        for idx, row in enumerate(rows):
            row['qualifies'] = idx < event.qualifiers_per_group
        groups.append({'group': group_name, 'rows': rows})

    knockout = None
    if event.matches.filter(round_number__gt=1).exists():
        knockout = compute_elimination_standings(event)
    return {'groups': groups, 'knockout': knockout}


def group_stage_overview(event):
    groups = OrderedDict()
    for match in event.matches.filter(group__isnull=False).order_by('group', 'id'):
        groups.setdefault(match.group, []).append(match)

    knockout_rounds = OrderedDict()
    for match in event.matches.filter(group__isnull=True).order_by('round_number', 'id'):
        knockout_rounds.setdefault(match.round_number, []).append(match)
    return groups, knockout_rounds


@transaction.atomic
def record_match_result(match, scores, notes=None, forfeited_side=None):
    """Record final scores for a match and advance winners in bracket formats.

    ``scores`` maps side -> Decimal (or str). At least one side must win; equal
    scores are treated as a draw (which cannot advance in elimination formats).
    """
    event = SportsEvent.objects.select_for_update().get(pk=match.event_id)
    match = Match.objects.select_for_update().get(pk=match.pk)
    if event.status in ('COMPLETED', 'CANCELLED'):
        raise ValueError('Reopen the event before changing match results.')
    if match.status in (Match.Status.COMPLETED, Match.Status.CANCELLED):
        raise ValueError('This match has already been completed.')

    entries = list(match.entries.all())
    if len(entries) != 2:
        raise ValueError('A match must have exactly two contestants to record a result.')

    if forfeited_side is not None:
        if forfeited_side not in (1, 2):
            raise ValueError('Choose the forfeiting side.')
        scores = {1: 0 if forfeited_side == 1 else 1, 2: 0 if forfeited_side == 2 else 1}
    parsed = {}
    for side in (1, 2):
        raw = scores.get(side)
        if raw in (None, ''):
            raise ValueError('Both sides must have a score.')
        try:
            value = Decimal(str(raw))
        except Exception:
            raise ValueError('Scores must be valid numbers.') from None
        if not value.is_finite() or value > Decimal('9999.99'):
            raise ValueError('Scores must be finite numbers no larger than 9999.99.')
        if value < 0:
            raise ValueError('Scores cannot be negative.')
        parsed[side] = value.quantize(Decimal('0.01'))

    if parsed[1] == parsed[2] and not (event.format == 'ROUND_ROBIN' or (event.format == 'LEAGUE' and (not event.playoff_count or match.group)) or match.group):
        raise ValueError('A deciding match cannot finish as a draw.')
    if event.format == 'BEST_OF' and event.matches.filter(round_number__lt=match.round_number).exclude(status='COMPLETED').exists():
        raise ValueError('Finish the preceding series games first.')

    with transaction.atomic():
        by_side = {entry.side: entry for entry in entries}
        for side, value in parsed.items():
            entry = by_side[side]
            entry.score = value
            entry.is_winner = False
            entry.is_draw = False
            entry.save(update_fields=['score', 'is_winner', 'is_draw'])

        first, second = entries[0], entries[1]
        if parsed[first.side] > parsed[second.side]:
            first.is_winner = True
        elif parsed[second.side] > parsed[first.side]:
            second.is_winner = True
        else:
            first.is_draw = True
            second.is_draw = True
        first.save(update_fields=['is_winner', 'is_draw'])
        second.save(update_fields=['is_winner', 'is_draw'])

        if match.group or event.format in ('ROUND_ROBIN', 'BEST_OF') or (event.format == 'LEAGUE' and not event.playoff_count):
            event.tie_resolution = []
            event.save(update_fields=['tie_resolution'])
        match.forfeited_side = forfeited_side
        if notes is not None:
            match.notes = notes
        match.status = Match.Status.COMPLETED
        match.save(update_fields=['status', 'notes', 'forfeited_side', 'updated_at'])

        winner = match.winner
        loser = first if second.is_winner else second if first.is_winner else None
        if winner is not None:
            if event.format == SportsEvent.Format.DOUBLE_ELIMINATION:
                _advance_double_elim(match, winner, loser, event)
                _resolve_double_byes(event)
            else:
                _advance_winner(match, winner)

        if event.format == SportsEvent.Format.GROUP_STAGE and match.group:
            try:
                _maybe_generate_group_knockout(event)
            except ValueError:
                pass  # Qualification ties remain visible for coordinator resolution.

        if event.format == 'LEAGUE' and event.playoff_count:
            try:
                _maybe_generate_league_playoffs(event)
            except ValueError:
                pass

        from .workflow import update_progress
        update_progress(event)

        return match


def _maybe_generate_group_knockout(event):
    """Auto-create the knockout stage once every group match is completed."""
    remaining_groups = event.matches.filter(group__isnull=False).exclude(
        status=Match.Status.COMPLETED,
    ).count()
    knockout_exists = event.matches.filter(round_number__gt=1).exists()
    if remaining_groups == 0 and not knockout_exists:
        qualifiers = _group_qualifiers(event)
        if len(qualifiers) >= 2:
            _build_elimination_matches(event, entries=qualifiers, start_round=2)


@transaction.atomic
def delete_bracket(event):
    event = SportsEvent.objects.select_for_update().get(pk=event.pk)
    if event.confirmed_at or event.matches.filter(status='COMPLETED', entries__score__isnull=False).exists():
        raise ValueError('Played fixtures cannot be deleted. Reopen and correct results instead.')
    event.matches.all().delete()
    event.status = 'REGISTRATION'
    event.save(update_fields=['status'])


def match_overview(event):
    """Return bracket-shaped match grouping: round number -> list of matches."""
    overview = {}
    for match in event.matches.all().order_by('round_number', 'id'):
        overview.setdefault(match.round_number, []).append(match)
    return overview


PODIUM_MEDALS = ('gold', 'silver', 'bronze')


def event_podium(event):
    """Derive the medal podium of a sport event from its own standings.

    Only a fully finished event yields medals, so a half-played bracket never
    publishes a provisional champion. Returns ``(entry, medal)`` tuples ordered
    gold, silver, bronze, where ``medal`` is one of :data:`PODIUM_MEDALS`.
    Events with fewer than two finishers return a partial or empty podium.
    """
    event = SportsEvent.objects.get(pk=event.pk)
    if event.status != 'COMPLETED' or not event.confirmed_at:
        return []
    return [(award.entry, award.medal) for award in event.confirmed_awards.select_related('entry__team', 'entry__participant').order_by('id')]


def find_venue_conflicts(venue, scheduled_start, scheduled_end, exclude_id=None):
    """Return matches at ``venue`` overlapping the given time window."""
    if venue is None or scheduled_start is None or scheduled_end is None:
        return []
    queryset = Match.objects.filter(
        venue=venue,
        status__in=[Match.Status.SCHEDULED, Match.Status.ONGOING, Match.Status.POSTPONED],
        scheduled_start__lt=scheduled_end,
        scheduled_end__gt=scheduled_start,
    )
    if exclude_id is not None:
        queryset = queryset.exclude(id=exclude_id)
    return list(queryset.select_related('event', 'event__sport_type', 'venue')[:20])

def _maybe_generate_league_playoffs(event):
    regular = event.matches.filter(group='League')
    if not regular.exists() or regular.exclude(status='COMPLETED').exists() or event.matches.filter(group__isnull=True).exists():
        return
    rows = _round_robin_standings(event, group='League')
    count = event.playoff_count
    if len(rows) > count and rows[count - 1]['rank'] == rows[count]['rank']:
        raise ValueError('Resolve the tied league qualification positions first.')
    # Seeding positions also affect the draw and must be resolved explicitly.
    if len({r['rank'] for r in rows[:count]}) != count:
        raise ValueError('Resolve tied playoff seeds first.')
    start = (event.matches.aggregate(Max('round_number'))['round_number__max'] or 0) + 1
    _build_elimination_matches(event, [r['entry'] for r in rows[:count]], start_round=start)


def _resolve_double_byes(event):
    """Advance a vacant path only after every possible feeder is resolved."""
    k, _ = _double_elim_rounds(event)
    grand = event.matches.filter(name='Grand Final').get()
    matches = list(event.matches.exclude(name='Grand Final Reset').order_by('round_number', 'id'))
    sources = {m.pk: set() for m in matches}
    for match in matches:
        if match.next_match_id:
            sources[match.next_match_id].add(match.pk)
        if match.name.startswith('WB Round'):
            r = match.round_number - 1
            peers = [m for m in matches if m.round_number == match.round_number]
            index = peers.index(match)
            if r == k - 1:
                target = next((m for m in matches if m.round_number == 3 * k - 2 and m.name.startswith('LB Round')), grand)
            else:
                targets = [m for m in matches if m.round_number == k + (1 if r == 0 else 2 * r)]
                target = targets[index // 2 if r == 0 else index]
            sources[target.pk].add(match.pk)
    while True:
        completed = set(event.matches.filter(status='COMPLETED').values_list('pk', flat=True))
        changed = False
        for match in event.matches.exclude(status='COMPLETED').exclude(name='Grand Final Reset').order_by('round_number', 'id'):
            entries = list(match.entries.all())
            if len(entries) >= 2 or not sources[match.pk] <= completed:
                continue
            match.status = 'COMPLETED'
            match.notes = 'Automatic bye; feeder paths resolved.'
            match.save(update_fields=['status', 'notes'])
            winner = entries[0] if entries else None
            if winner:
                winner.is_winner = True
                winner.save(update_fields=['is_winner'])
            _advance_double_elim(match, winner, None, event)
            changed = True
        if not changed:
            break
