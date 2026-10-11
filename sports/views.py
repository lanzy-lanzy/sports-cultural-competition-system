from collections import OrderedDict, defaultdict
from datetime import datetime

from django.contrib import messages
from django.db import transaction
from django.db.models import Count, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from competitions.models import Competition
from accounts.access import management_required
from .forms import EventEntryForm, MatchForm, SportsEventForm, SportTypeForm, VenueForm
from .models import EventEntry, Match, SportsEvent, SportType, Venue
from .services import (
    compute_elimination_standings,
    compute_group_stage_standings,
    compute_standings,
    delete_bracket,
    generate_bracket,
    group_stage_overview,
    match_overview,
    record_match_result,
)
from audit.models import record_action_from_request


@management_required
def sports_hub(request):
    """Landing page for sports coordinators: counts, navigation, and today's work."""
    now = timezone.now()

    competitions = (
        Competition.objects
        .filter(sport_events__isnull=False)
        .distinct()
        .order_by('-start_date')
    )

    events = (
        SportsEvent.objects
        .filter(competition__in=competitions)
        .select_related('competition', 'sport_type', 'venue')
        .annotate(
            match_total=Count('matches', distinct=True),
            match_done=Count(
                'matches', distinct=True,
                filter=Q(matches__status=Match.Status.COMPLETED),
            ),
            entry_confirmed=Count(
                'entries', distinct=True,
                filter=Q(entries__status=EventEntry.Status.CONFIRMED),
            ),
            entry_total=Count('entries', distinct=True),
        )
    )

    events_by_competition = defaultdict(list)
    for event in events:
        events_by_competition[event.competition_id].append(event)

    competition_rows = []
    for competition in competitions:
        competition_events = events_by_competition.get(competition.id, [])
        match_total = sum(event.match_total for event in competition_events)
        match_done = sum(event.match_done for event in competition_events)
        competition_rows.append({
            'competition': competition,
            'events': competition_events,
            'match_total': match_total,
            'match_done': match_done,
        })

    base = Match.objects.select_related(
        'event', 'event__competition', 'event__sport_type', 'venue',
    ).prefetch_related('entries__team', 'entries__participant')

    overdue = (
        base
        .filter(status=Match.Status.SCHEDULED, scheduled_start__lt=now)
        .order_by('scheduled_start')[:6]
    )
    upcoming = (
        base
        .filter(
            status__in=[Match.Status.SCHEDULED, Match.Status.ONGOING],
            scheduled_start__gte=now,
        )
        .order_by('scheduled_start')[:8]
    )
    today = now.date()

    return render(request, 'sports/sports_hub.html', {
        'competition_rows': competition_rows,
        'stats': {
            'sport_types': SportType.objects.filter(is_active=True).count(),
            'venues': Venue.objects.filter(is_active=True).count(),
            'events': sum(len(row['events']) for row in competition_rows),
            'matches': Match.objects.count(),
            'completed': Match.objects.filter(status=Match.Status.COMPLETED).count(),
            'awaiting': Match.objects.filter(status=Match.Status.SCHEDULED).count(),
            'overdue': base.filter(status=Match.Status.SCHEDULED, scheduled_start__lt=now).count(),
        },
        'overdue': list(overdue),
        'upcoming': list(upcoming),
        'today': today,
    })


@management_required
def match_board(request):
    """Every match across every competition, filtered and grouped by day."""
    matches = Match.objects.select_related(
        'event', 'event__competition', 'event__sport_type', 'venue',
    ).prefetch_related('entries__team', 'entries__participant')

    competition_id = request.GET.get('competition', '')
    sport_id = request.GET.get('sport', '')
    venue_id = request.GET.get('venue', '')
    status = request.GET.get('status', '')
    day = request.GET.get('day', '')

    if competition_id.isdigit():
        matches = matches.filter(event__competition_id=int(competition_id))
    if sport_id.isdigit():
        matches = matches.filter(event__sport_type_id=int(sport_id))
    if venue_id.isdigit():
        matches = matches.filter(venue_id=int(venue_id))
    if status in Match.Status.values:
        matches = matches.filter(status=status)

    # Validate the day before filtering; a bad value simply clears the filter.
    selected_day = None
    if day:
        try:
            selected_day = datetime.strptime(day, '%Y-%m-%d').date()
        except ValueError:
            day = ''

    matches = matches.order_by('scheduled_start', 'venue__name', 'id')

    # Group by day across every other active filter so the day tabs and the
    # previous/next links can still reach the neighbouring days.
    all_days = OrderedDict()
    unscheduled = []
    for match in matches:
        if match.scheduled_start:
            local_day = timezone.localtime(match.scheduled_start).date()
            all_days.setdefault(local_day, []).append(match)
        elif selected_day is None:
            unscheduled.append(match)
    all_days = OrderedDict(sorted(all_days.items(), key=lambda item: item[0]))

    day_keys = list(all_days)
    if selected_day is None:
        days = all_days
        selected_index = None
    else:
        days = OrderedDict()
        if selected_day in all_days:
            days[selected_day] = all_days[selected_day]
        selected_index = day_keys.index(selected_day) if selected_day in all_days else None

    total = sum(len(day_matches) for day_matches in days.values()) + len(unscheduled)

    # Guard the bounds explicitly: day_keys[-1] would wrap to the last day.
    prev_day = next_day = None
    if selected_index is not None:
        if selected_index > 0:
            prev_day = day_keys[selected_index - 1]
        if selected_index < len(day_keys) - 1:
            next_day = day_keys[selected_index + 1]

    filter_state = {
        'competition': competition_id,
        'sport': sport_id,
        'venue': venue_id,
        'status': status,
        'day': day,
    }
    active_count = sum(1 for value in filter_state.values() if value)

    return render(request, 'sports/match_board.html', {
        'days': days,
        'unscheduled': unscheduled,
        'day_keys': day_keys,
        'selected_index': selected_index,
        'prev_day': prev_day,
        'next_day': next_day,
        'total': total,
        'active_count': active_count,
        'filter_state': filter_state,
        'competitions': Competition.objects.order_by('-start_date'),
        'sport_types': SportType.objects.order_by('name'),
        'venues': Venue.objects.order_by('name'),
        'statuses': Match.Status.choices,
    })


@management_required
def sport_type_list(request):
    types = SportType.objects.all().order_by('name')
    return render(request, 'sports/sport_type_list.html', {'types': types})


@management_required
def sport_type_create(request):
    form = SportTypeForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Sport type added successfully.')
        return redirect('sport_type_list')
    return render(request, 'sports/sport_type_form.html', {'form': form, 'sport_type': None})


@management_required
def sport_type_edit(request, sport_type_id):
    sport_type = get_object_or_404(SportType, id=sport_type_id)
    form = SportTypeForm(request.POST or None, instance=sport_type)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Sport type updated successfully.')
        return redirect('sport_type_list')
    return render(request, 'sports/sport_type_form.html', {'form': form, 'sport_type': sport_type})


@management_required
def venue_list(request):
    venues = Venue.objects.all().order_by('name')
    return render(request, 'sports/venue_list.html', {'venues': venues})


@management_required
def venue_create(request):
    form = VenueForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Venue added successfully.')
        return redirect('venue_list')
    return render(request, 'sports/venue_form.html', {'form': form, 'venue': None})


@management_required
def venue_edit(request, venue_id):
    venue = get_object_or_404(Venue, id=venue_id)
    form = VenueForm(request.POST or None, instance=venue)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Venue updated successfully.')
        return redirect('venue_list')
    return render(request, 'sports/venue_form.html', {'form': form, 'venue': venue})


@management_required
def competition_sport_events(request, competition_id):
    competition = get_object_or_404(Competition, id=competition_id)
    events = competition.sport_events.all().order_by('sport_type__name', 'name')
    for event in events:
        event.match_count = event.matches.count()
        event.completed_count = event.matches.filter(status=Match.Status.COMPLETED).count()
    return render(request, 'sports/event_list.html', {'competition': competition, 'events': events})


@management_required
def create_sport_event(request, competition_id):
    competition = get_object_or_404(Competition, id=competition_id)
    form = SportsEventForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        event = form.save(commit=False)
        event.competition = competition
        if not event.name.strip():
            event.name = f'{event.sport_type.name} - {event.get_gender_display()}'
        event.save()
        messages.success(request, f'{event.name} was created.')
        return redirect('sport_event_detail', event_id=event.id)
    return render(request, 'sports/event_form.html', {'form': form, 'competition': competition, 'event': None})


@management_required
def edit_sport_event(request, event_id):
    event = get_object_or_404(SportsEvent, id=event_id)
    form = SportsEventForm(request.POST or None, instance=event)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Event details updated successfully.')
        return redirect('sport_event_detail', event_id=event.id)
    return render(request, 'sports/event_form.html', {'form': form, 'competition': event.competition, 'event': event})


@management_required
def sport_event_detail(request, event_id):
    event = get_object_or_404(SportsEvent.objects.select_related('competition', 'sport_type', 'venue'), id=event_id)
    entries = event.entries.select_related('team', 'participant').order_by('seed', 'id')
    matches = event.matches.select_related('venue').order_by('round_number', 'id')
    return render(request, 'sports/event_detail.html', {
        'event': event,
        'entries': entries,
        'matches': matches,
        'overview': match_overview(event),
        'entry_form': EventEntryForm(event=event),
        'bracket_generated': event.matches.exists(),
    })


@management_required
@require_POST
def add_event_entry(request, event_id):
    event = get_object_or_404(SportsEvent, id=event_id)
    form = EventEntryForm(request.POST, event=event)
    if form.is_valid():
        EventEntry.objects.create(
            event=event,
            team=form.cleaned_data['team'],
            participant=form.cleaned_data['participant'],
            status=EventEntry.Status.CONFIRMED,
        )
        messages.success(request, 'Entry added to the event.')
    else:
        for field_errors in form.errors.values():
            for error in field_errors:
                messages.error(request, error)
    return redirect('sport_event_detail', event_id=event.id)


@management_required
@require_POST
def update_entry_status(request, event_id, entry_id):
    event = get_object_or_404(SportsEvent, id=event_id)
    entry = get_object_or_404(EventEntry, id=entry_id, event=event)
    status = request.POST.get('status')
    if status in EventEntry.Status.values:
        entry.status = status
        entry.save(update_fields=['status'])
        messages.success(request, f'{entry.display_name} is now {entry.get_status_display()}.')
    else:
        messages.error(request, 'Invalid entry status.')
    return redirect('sport_event_detail', event_id=event.id)


@management_required
@require_POST
def remove_event_entry(request, event_id, entry_id):
    event = get_object_or_404(SportsEvent, id=event_id)
    entry = get_object_or_404(EventEntry, id=entry_id, event=event)
    name = entry.display_name
    entry.delete()
    messages.success(request, f'{name} was removed from the event.')
    return redirect('sport_event_detail', event_id=event.id)


@management_required
@require_POST
def generate_event_bracket(request, event_id):
    event = get_object_or_404(SportsEvent, id=event_id)
    try:
        generate_bracket(event)
        record_action_from_request(
            request,
            'BRACKET_GENERATED',
            target=event,
            details=f'Bracket generated for {event.name}',
        )
        messages.success(request, 'Tournament bracket generated successfully.')
    except ValueError as error:
        messages.error(request, str(error))
    return redirect('sport_event_detail', event_id=event.id)


@management_required
@require_POST
def clear_event_bracket(request, event_id):
    event = get_object_or_404(SportsEvent, id=event_id)
    delete_bracket(event)
    record_action_from_request(
        request,
        'BRACKET_CLEARED',
        target=event,
        details=f'Bracket cleared for {event.name}',
    )
    messages.success(request, 'Bracket and matches cleared.')
    return redirect('sport_event_detail', event_id=event.id)


@management_required
def match_schedule(request, event_id):
    event = get_object_or_404(SportsEvent.objects.select_related('competition'), id=event_id)
    matches = event.matches.select_related('venue').order_by('round_number', 'id')
    return render(request, 'sports/match_schedule.html', {'event': event, 'matches': matches})


@management_required
def edit_match(request, match_id):
    match = get_object_or_404(Match.objects.select_related('event__competition'), id=match_id)
    form = MatchForm(request.POST or None, instance=match)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Match schedule updated.')
        return redirect('match_schedule', event_id=match.event_id)
    return render(request, 'sports/match_form.html', {'form': form, 'match': match})


@management_required
@require_POST
def record_match_result_view(request, match_id):
    match = get_object_or_404(Match.objects.select_related('event'), id=match_id)
    scores = {
        1: request.POST.get('score_1'),
        2: request.POST.get('score_2'),
    }
    wants_json = request.POST.get('format') == 'json'
    try:
        record_match_result(match, scores, notes=request.POST.get('notes', ''))
        record_action_from_request(
            request,
            'MATCH_RESULT',
            target=match,
            details=f'Result recorded for {match.event.name} - {match.label}',
        )
        if wants_json:
            return JsonResponse({'ok': True, 'bracket': bracket_payload(match.event)})
        messages.success(request, 'Match result recorded.')
    except ValueError as error:
        if wants_json:
            return JsonResponse({'ok': False, 'error': str(error)}, status=400)
        messages.error(request, str(error))
    return redirect('match_schedule', event_id=match.event_id)


@management_required
def event_standings(request, event_id):
    event = get_object_or_404(SportsEvent.objects.select_related('competition'), id=event_id)
    if event.format == SportsEvent.Format.GROUP_STAGE:
        return render(request, 'sports/group_standings.html', {
            'event': event,
            'group_stage': compute_group_stage_standings(event),
        })
    standings = compute_standings(event)
    return render(request, 'sports/event_standings.html', {'event': event, 'standings': standings})


ROUND_LABELS = {2: 'Final', 4: 'Semifinals', 8: 'Quarterfinals'}


def _bracket_match_brief(match):
    return {
        'id': match.id,
        'label': match.label,
        'status': match.status,
        'statusDisplay': match.get_status_display(),
        'next': match.next_match_id,
        'venue': match.venue.name if match.venue_id else None,
        'start': timezone.localtime(match.scheduled_start).strftime('%b %d · %H:%M') if match.scheduled_start else None,
        'recordUrl': reverse('record_match_result', args=[match.id]),
        'entries': [
            {
                'side': entry.side,
                'name': entry.display_name,
                'score': float(entry.score) if entry.score is not None else None,
                'winner': entry.is_winner,
                'draw': entry.is_draw,
            }
            for entry in match.entries.all()
        ],
    }


def bracket_payload(event):
    """Bracket-shaped JSON for the interactive bracket page.

    Only elimination brackets (no group matches) get the connector layout; the
    template falls back to the plain round grid for other formats.
    """
    if event.format not in (SportsEvent.Format.SINGLE_ELIMINATION, SportsEvent.Format.KNOCKOUT):
        return None
    matches = (
        event.matches
        .select_related('venue', 'next_match')
        .prefetch_related('entries__team', 'entries__participant')
        .order_by('round_number', 'id')
    )
    by_round = OrderedDict()
    for match in matches:
        if match.group:
            continue
        by_round.setdefault(match.round_number, []).append(match)
    if not by_round:
        return None

    rounds = []
    for round_number, round_matches in by_round.items():
        slots = 2 * len(round_matches)
        rounds.append({
            'label': ROUND_LABELS.get(slots) or f'Round of {slots}',
            'done': sum(1 for m in round_matches if m.status == Match.Status.COMPLETED),
            'total': len(round_matches),
            'matches': [_bracket_match_brief(m) for m in round_matches],
        })

    champion = None
    final_matches = list(by_round.values())[-1]
    if len(final_matches) == 1:
        winner = final_matches[0].winner
        if winner and final_matches[0].status == Match.Status.COMPLETED:
            champion = winner.display_name

    return {'rounds': rounds, 'champion': champion}


@management_required
def event_bracket(request, event_id):
    event = get_object_or_404(SportsEvent.objects.select_related('competition'), id=event_id)
    if event.format == SportsEvent.Format.GROUP_STAGE:
        groups, knockout_rounds = group_stage_overview(event)
        return render(request, 'sports/group_bracket.html', {
            'event': event,
            'groups': groups,
            'knockout_rounds': knockout_rounds,
        })
    bracket = bracket_payload(event)
    if request.GET.get('format') == 'json':
        return JsonResponse(bracket or {'rounds': [], 'champion': None})
    return render(request, 'sports/event_bracket.html', {
        'event': event,
        'bracket': bracket,
        'overview': match_overview(event),
    })


@management_required
def venue_detail(request, venue_id):
    venue = get_object_or_404(
        Venue.objects.prefetch_related('events'),
        id=venue_id,
    )
    events = venue.events.order_by('-start_date')
    matches = (
        venue.matches.select_related('event', 'event__sport_type', 'event__competition')
        .order_by('scheduled_start', 'id')
    )
    upcoming = [m for m in matches if m.status != Match.Status.COMPLETED]
    completed = [m for m in matches if m.status == Match.Status.COMPLETED]
    return render(request, 'sports/venue_detail.html', {
        'venue': venue,
        'events': events,
        'matches': matches,
        'upcoming': upcoming,
        'completed': completed,
    })