"""Sports tournament completion, placements and confirmed medal publication."""
from collections import Counter
from django.db import transaction
from django.utils import timezone
from audit.models import record_action
from .models import EventAward, Match, SportsEvent


def identity(entry):
    return (entry.team_id, entry.participant_id)


def rank_table(event, rows, group=None):
    """Competition ranks: unresolved sporting ties retain a shared rank."""
    breakers = event.tiebreakers or ['point_diff', 'points_for']
    for row in rows:
        row['_key'] = [row['wins'] if event.format == 'BEST_OF' else row['total_points']]
    for breaker in breakers:
        cohorts = {}
        for row in rows:
            cohorts.setdefault(tuple(row['_key']), []).append(row)
        for cohort in cohorts.values():
            ids = {identity(r['entry']) for r in cohort}
            for row in cohort:
                value = row.get(breaker, 0)
                if breaker == 'head_to_head':
                    value = 0
                    for match in event.matches.filter(status='COMPLETED').prefetch_related('entries'):
                        if group and match.group != group:
                            continue
                        entries = list(match.entries.all())
                        if len(entries) != 2 or not all(identity(e) in ids for e in entries):
                            continue
                        own = next((e for e in entries if identity(e) == identity(row['entry'])), None)
                        if own:
                            value += event.win_points if own.is_winner else event.draw_points if own.is_draw else event.loss_points
                row['_key'].append(value)
    resolution = event.tie_resolution or []
    if set(resolution) >= {r['entry'].pk for r in rows}:
        for row in rows:
            row['_key'].append(-resolution.index(row['entry'].pk))
    rows.sort(key=lambda r: tuple(-v for v in r['_key']))
    previous = None
    rank = 0
    for index, row in enumerate(rows, 1):
        key = tuple(row['_key'])
        if key != previous:
            rank = index
        row['rank'] = rank
        previous = key
    return rows


def final_match(event):
    return event.matches.filter(group__isnull=True).exclude(name='Bronze Match').order_by('-round_number', '-id').first()


def _event_entry(event, match_entry):
    entry = event.entries.filter(team_id=match_entry.team_id, participant_id=match_entry.participant_id, status='CONFIRMED').first()
    if entry is None:
        raise ValueError('A match contestant is missing from confirmed event entries. Correct registration before confirming awards.')
    return entry


def proposed_podium(event):
    from .services import compute_standings
    if not event.matches.exists():
        raise ValueError('Generate and finish the fixtures first.')
    if event.status == 'CANCELLED':
        raise ValueError('Cancelled events cannot issue awards.')
    active = event.matches.exclude(status='CANCELLED')
    if active.exclude(status='COMPLETED').exists():
        raise ValueError('Finish every required match before confirming awards.')
    # Cancellation never turns an unfinished tournament into a completed one.
    if event.format != 'BEST_OF' and event.matches.filter(status='CANCELLED').exists():
        raise ValueError('Cancelled fixtures must be resolved before confirming awards.')
    if event.format in ('ROUND_ROBIN', 'BEST_OF') or (event.format == 'LEAGUE' and not event.playoff_count):
        rows = compute_standings(event)
        if event.format == 'BEST_OF' and (not rows or rows[0]['wins'] < event.best_of // 2 + 1):
            raise ValueError('The series has not been clinched.')
        needed = 2 if event.bronze_policy == 'NONE' else min(3, len(rows))
        for row in rows[:needed]:
            if sum(r['rank'] == row['rank'] for r in rows) > 1:
                raise ValueError('Resolve tied medal positions before confirming awards.')
        return [(r['entry'], medal) for r, medal in zip(rows[:needed], ('gold', 'silver', 'bronze'))]
    if (event.format == 'GROUP_STAGE' or (event.format == 'LEAGUE' and event.playoff_count)) and not event.matches.filter(group__isnull=True).exists():
        raise ValueError('Resolve group qualification and finish the knockout stage first.')
    final = final_match(event)
    if not final or not final.winner or final.entries.count() != 2:
        raise ValueError('The deciding final must have a winner and runner-up.')
    winner = final.winner
    runner = final.entries.exclude(pk=winner.pk).get()
    podium = [(_event_entry(event, winner), 'gold'), (_event_entry(event, runner), 'silver')]
    if event.bronze_policy == 'NONE':
        return podium
    if event.format == 'DOUBLE_ELIMINATION':
        last_lb = event.matches.filter(name__startswith='LB Round').order_by('-round_number').first()
        if last_lb and last_lb.winner:
            loser = last_lb.entries.exclude(is_winner=True).get()
            podium.append((_event_entry(event, loser), 'bronze'))
        return podium
    semis = list(final.previous_matches.all())
    losers = [m.entries.exclude(is_winner=True).first() for m in semis if m.winner and m.entries.count() == 2]
    if event.bronze_policy == 'MATCH' and len(losers) == 2:
        bronze = event.matches.filter(name='Bronze Match').first()
        if not bronze or not bronze.winner:
            raise ValueError('Finish the third-place match first.')
        podium.append((_event_entry(event, bronze.winner), 'bronze'))
    else:
        podium.extend((_event_entry(event, loser), 'bronze') for loser in losers)
    return podium


def update_progress(event):
    from .services import _place_entry
    if event.format == 'BEST_OF':
        wins = Counter(identity(e) for m in event.matches.filter(status='COMPLETED') for e in m.entries.filter(is_winner=True))
        if wins and max(wins.values()) >= event.best_of // 2 + 1:
            event.matches.exclude(status='COMPLETED').update(status='CANCELLED', notes='Series clinched; game not required.')
    elif event.bronze_policy == 'MATCH' and event.format in ('SINGLE_ELIMINATION', 'KNOCKOUT', 'GROUP_STAGE', 'LEAGUE'):
        final = final_match(event)
        semis = list(final.previous_matches.all()) if final else []
        if len(semis) == 2 and all(m.status == 'COMPLETED' for m in semis):
            losers = [m.entries.exclude(is_winner=True).first() for m in semis if m.entries.count() == 2]
            if len(losers) == 2 and not event.matches.filter(name='Bronze Match').exists():
                bronze = Match.objects.create(event=event, name='Bronze Match', round_number=final.round_number)
                for side, loser in enumerate(losers, 1):
                    _place_entry(bronze, loser, side)
    try:
        proposed_podium(event)
        event.status = 'REVIEW'
    except ValueError:
        event.status = 'ONGOING'
    event.save(update_fields=['status'])


@transaction.atomic
def confirm_awards(event, user):
    event = SportsEvent.objects.select_for_update().get(pk=event.pk)
    if event.confirmed_at:
        return  # Idempotent confirmation.
    podium = proposed_podium(event)
    EventAward.objects.filter(event=event).delete()
    EventAward.objects.bulk_create([EventAward(event=event, entry=entry, medal=medal) for entry, medal in podium])
    event.status = 'COMPLETED'
    event.confirmed_at = timezone.now()
    event.confirmed_by = user
    event.save(update_fields=['status', 'confirmed_at', 'confirmed_by'])
    record_action(user, 'AWARD_CHANGE', event, 'Confirmed sports podium: ' + ', '.join(f'{e.display_name}: {m}' for e, m in podium))
    competition = type(event.competition).objects.select_for_update().get(pk=event.competition_id)
    if not competition.sport_events.exclude(status__in=['COMPLETED', 'CANCELLED']).exists():
        competition.status = 'COMPLETED'
        competition.save(update_fields=['status'])


@transaction.atomic
def reopen_event(event, user, reason):
    if not reason.strip():
        raise ValueError('Enter a reason for reopening the event.')
    event = SportsEvent.objects.select_for_update().get(pk=event.pk)
    event.confirmed_awards.all().delete()
    event.confirmed_at = None
    event.confirmed_by = None
    event.status = 'ONGOING' if event.matches.exists() else 'REGISTRATION'
    event.save(update_fields=['status', 'confirmed_at', 'confirmed_by'])
    if event.competition.status == 'COMPLETED':
        event.competition.status = 'ACTIVE'
        event.competition.save(update_fields=['status'])
    record_action(user, 'AWARD_CHANGE', event, 'Reopened event and withdrew confirmed medals: ' + reason)


@transaction.atomic
def resolve_ties(event, user, order, reason):
    event = SportsEvent.objects.select_for_update().get(pk=event.pk)
    if event.confirmed_at or not reason.strip():
        raise ValueError('Reopen confirmed awards first and provide the tie resolution reason.')
    ids = set(event.entries.filter(status='CONFIRMED').values_list('pk', flat=True))
    if len(order) != len(ids) or set(order) != ids:
        raise ValueError('Enter every confirmed entry ID exactly once, in the approved tie-break order.')
    event.tie_resolution = order
    event.save(update_fields=['tie_resolution'])
    record_action(user, 'MATCH_RESULT', event, f'Tie resolution {order}: {reason}')
    if event.format == 'GROUP_STAGE':
        from .services import _maybe_generate_group_knockout
        _maybe_generate_group_knockout(event)
    if event.format == 'LEAGUE' and event.playoff_count:
        from .services import _maybe_generate_league_playoffs
        _maybe_generate_league_playoffs(event)
    update_progress(event)


@transaction.atomic
def correct_result(match, user, scores, reason):
    """Invalidate dependent results before replaying a corrected fixture."""
    from .services import record_match_result
    event = SportsEvent.objects.select_for_update().get(pk=match.event_id)
    match = Match.objects.select_for_update().get(pk=match.pk)
    if event.confirmed_at or not reason.strip():
        raise ValueError('Reopen the event and enter a correction reason first.')
    if match.status != 'COMPLETED' or match.entries.count() != 2:
        raise ValueError('Only a played match can be corrected.')
    if event.format in ('DOUBLE_ELIMINATION', 'BEST_OF'):
        # Later rounds can depend on either the winner or loser of this result.
        later = event.matches.filter(round_number__gt=match.round_number)
    elif match.group:
        later = event.matches.filter(group__isnull=True)
    else:
        ids = []
        target = match.next_match
        while target:
            ids.append(target.pk)
            target = target.next_match
        later = event.matches.filter(pk__in=ids)
    for dependent in later:
        if event.format == 'BEST_OF':
            dependent.entries.update(score=None, is_winner=False, is_draw=False)
            dependent.status = 'SCHEDULED'
            dependent.save(update_fields=['status'])
        elif match.group:
            dependent.delete()
        else:
            dependent.entries.all().delete()
            dependent.status = 'SCHEDULED'
            dependent.save(update_fields=['status'])
    if event.format not in ('BEST_OF', 'ROUND_ROBIN') and not (event.format == 'LEAGUE' and not event.playoff_count):
        event.matches.filter(name='Bronze Match').exclude(pk=match.pk).delete()
    event.tie_resolution = []
    event.save(update_fields=['tie_resolution'])
    match.entries.update(score=None, is_winner=False, is_draw=False)
    match.status = 'SCHEDULED'
    match.save(update_fields=['status'])
    if event.format == 'DOUBLE_ELIMINATION' and match.name != 'Grand Final Reset':
        event.matches.filter(name='Grand Final Reset').delete()
    # Refill invalidated bracket slots from results which remain valid.
    from .services import _advance_winner, _advance_double_elim
    for previous in event.matches.filter(status='COMPLETED').order_by('round_number', 'pk'):
        if previous.winner:
            if event.format == 'DOUBLE_ELIMINATION':
                _advance_double_elim(previous, previous.winner, previous.entries.exclude(is_winner=True).first(), event)
            else:
                _advance_winner(previous, previous.winner)
    record_match_result(match, scores)
    record_action(user, 'MATCH_RESULT', match, 'Corrected result; dependent results invalidated: ' + reason)


@transaction.atomic
def seed_entries(event, user, order):
    event = SportsEvent.objects.select_for_update().get(pk=event.pk)
    if event.matches.exists() or event.confirmed_at:
        raise ValueError('Clear unplayed fixtures before changing seeds.')
    entries = list(event.entries.filter(status='CONFIRMED'))
    if len(order) != len(entries) or set(order) != {e.pk for e in entries}:
        raise ValueError('Include every confirmed entry ID exactly once in seed order.')
    for entry in entries:
        entry.seed = order.index(entry.pk) + 1
    if entries:
        type(entries[0]).objects.bulk_update(entries, ['seed'])
    record_action(user, 'BRACKET_GENERATED', event, f'Seeds configured: {order}')
