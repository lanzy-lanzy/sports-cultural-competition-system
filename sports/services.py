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
    for _ in range(n - 1):
        pairs = []
        for i in range(len(teams) // 2):
            pairs.append((teams[i], teams[len(teams) - 1 - i]))
        rounds_pairs.append(pairs)
        teams = [teams[0]] + [teams[-1]] + teams[1:-1]

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

    if n <= 4:
        group_count = 1
    elif n <= 8:
        group_count = 2
    else:
        group_count = 4
    group_count = min(group_count, n)

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
        for round_number, pairs in enumerate(pairs_rounds, start=1):
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

    Requires a power-of-two number of confirmed entries to guarantee a balanced
    losers bracket with no dead slots.
    """
    entries = list(event.entries.filter(status='CONFIRMED').order_by('seed', 'id'))
    n = len(entries)
    if n < 2:
        return []
    if n & (n - 1):
        raise ValueError(
            'Double elimination requires a power-of-two number of confirmed entries '
            '(2, 4, 8, ...). Add or withdraw entries first, or use another format.'
        )

    size = n
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

    if grand is not None and round_no == grand.round_number:
        # Grand final decided the champion.
        return

    if round_no <= k:
        # Winners bracket.
        r = round_no - 1
        if r == k - 1:
            # WB final: winner -> grand (side 1), loser -> last LB round (side 2).
            if grand is not None:
                _place_entry(grand, winner, 1)
            last_lb = event.matches.filter(round_number=3 * k - 2).order_by('id').first()
            if last_lb is not None:
                _place_entry(last_lb, loser, 2)
            return
        _advance_winner(match, winner)
        peers = list(Match.objects.filter(event=event, round_number=round_no).order_by('id'))
        try:
            idx = peers.index(match)
        except ValueError:
            return
        lb_round = list(event.matches.filter(round_number=k + 2 * r + 1).order_by('id'))
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
    if event.matches.exists():
        raise ValueError('A bracket has already been generated. Delete existing matches first.')
    if not event.can_generate_bracket():
        raise ValueError('At least two confirmed entries are required to generate a bracket.')

    if event.format in (SportsEvent.Format.SINGLE_ELIMINATION, SportsEvent.Format.KNOCKOUT):
        _build_elimination_matches(event)
    elif event.format == SportsEvent.Format.ROUND_ROBIN:
        _generate_round_robin(event)
    elif event.format == SportsEvent.Format.DOUBLE_ELIMINATION:
        _generate_double_elimination(event)
    elif event.format == SportsEvent.Format.GROUP_STAGE:
        _generate_group_stage(event)
    else:
        raise ValueError(f'Bracket generation is not supported for {event.get_format_display()}.')


def _entry_matches_query(event, entry, group=None, knockout_only=False):
    from django.db.models import Q

    base = event.matches.filter(status=Match.Status.COMPLETED)
    if group:
        base = base.filter(group=group)
    if knockout_only:
        base = base.filter(group__isnull=True)
    if entry.team_id:
        return base.filter(entries__team=entry.team)
    return base.filter(entries__participant=entry.participant)


def _round_robin_standings(event, group=None):
    rows = []
    for entry in event.entries.filter(status='CONFIRMED'):
        completed = list(_entry_matches_query(event, entry, group=group).distinct())
        played = len(completed)
        wins = 0
        draws = 0
        losses = 0
        points_for = Decimal('0')
        points_against = Decimal('0')

        for match in completed:
            match_entries = list(match.entries.all())
            own = next(
                (me for me in match_entries
                 if (entry.team_id and me.team_id == entry.team_id)
                 or (entry.participant_id and me.participant_id == entry.participant_id)),
                None,
            )
            opponent = next((me for me in match_entries if me.id != own.id), None)
            if own is None or own.score is None:
                continue
            if own.is_winner:
                wins += 1
            elif own.is_draw:
                draws += 1
            else:
                losses += 1
            points_for += own.score
            if opponent and opponent.score is not None:
                points_against += opponent.score

        total_points = wins * 3 + draws
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

    rows.sort(key=lambda row: (-row['total_points'], -row['point_diff'], -row['points_for']))
    for idx, row in enumerate(rows, start=1):
        row['rank'] = idx
    return rows


def compute_elimination_standings(event):
    """Standings for elimination formats derived from the bracket structure.

    The champion ranks first, followed by the runner-up, then contestants ordered
    by how deep into the bracket they were eliminated.
    """
    final_round = event.matches.aggregate(Max('round_number'))['round_number__max'] or 0
    has_groups = event.matches.filter(group__isnull=False).exists()

    entries = event.entries.filter(status='CONFIRMED')
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
        for match in completed:
            own = next(
                (me for me in match.entries.all()
                 if (entry.team_id and me.team_id == entry.team_id)
                 or (entry.participant_id and me.participant_id == entry.participant_id)),
                None,
            )
            if own is None:
                continue
            if own.is_winner:
                wins += 1
            else:
                losses += 1
                last_lost_round = max(last_lost_round, match.round_number)

        is_champion = False
        for match in completed:
            if match.round_number != final_round:
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
            'played': len(completed),
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
    return rows


def compute_standings(event):
    """Standings appropriate to the event format."""
    if event.format in (SportsEvent.Format.ROUND_ROBIN, SportsEvent.Format.GROUP_STAGE):
        return _round_robin_standings(event)
    return compute_elimination_standings(event)


def compute_group_standings(event, group_name):
    return _round_robin_standings(event, group=group_name)


def _group_qualifiers(event):
    """Top two entries of each group, ordered by group letter then points."""
    groups = (
        Match.objects.filter(event=event, group__isnull=False)
        .values_list('group', flat=True)
        .distinct()
        .order_by('group')
    )
    qualifiers = []
    for group_name in groups:
        rows = compute_group_standings(event, group_name)
        qualifiers.extend(row['entry'] for row in rows[:2])
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
            row['qualifies'] = idx < 2
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
def record_match_result(match, scores, notes=None):
    """Record final scores for a match and advance winners in bracket formats.

    ``scores`` maps side -> Decimal (or str). At least one side must win; equal
    scores are treated as a draw (which cannot advance in elimination formats).
    """
    if match.status == Match.Status.COMPLETED:
        raise ValueError('This match has already been completed.')

    entries = list(match.entries.all())
    if len(entries) != 2:
        raise ValueError('A match must have exactly two contestants to record a result.')

    parsed = {}
    for side in (1, 2):
        raw = scores.get(side)
        if raw in (None, ''):
            raise ValueError('Both sides must have a score.')
        try:
            value = Decimal(str(raw))
        except Exception:
            raise ValueError('Scores must be valid numbers.') from None
        if value < 0:
            raise ValueError('Scores cannot be negative.')
        parsed[side] = value.quantize(Decimal('0.01'))

    event = match.event

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

        if notes is not None:
            match.notes = notes
        match.status = Match.Status.COMPLETED
        match.save(update_fields=['status', 'notes', 'updated_at'])

        winner = match.winner
        loser = first if second.is_winner else second if first.is_winner else None
        if winner is not None:
            if event.format == SportsEvent.Format.DOUBLE_ELIMINATION:
                _advance_double_elim(match, winner, loser, event)
            else:
                _advance_winner(match, winner)

        if event.format == SportsEvent.Format.GROUP_STAGE and match.group:
            _maybe_generate_group_knockout(event)

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


def delete_bracket(event):
    event.matches.all().delete()


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
    matches = event.matches.all()
    if not matches.exists():
        return []
    if matches.exclude(status=Match.Status.COMPLETED).exists():
        return []

    if event.format == SportsEvent.Format.GROUP_STAGE:
        # The knockout stage decides the medals, not the group tables.
        standings = compute_group_stage_standings(event)['knockout'] or []
    else:
        standings = compute_standings(event)

    podium = []
    for medal, position in zip(PODIUM_MEDALS, (1, 2, 3)):
        # Ties share a rank, so take the first row holding that position.
        for row in standings:
            if row['rank'] == position:
                podium.append((row['entry'], medal))
                break
    return podium


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