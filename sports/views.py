from collections import OrderedDict, defaultdict
from datetime import datetime

from django.contrib import messages
from django.db import transaction
from django.db.models import Count, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from competitions.models import Competition
from accounts.access import management_required
from .forms import BoardManualMatchForm, EventEntryForm, ManualMatchForm, SportsEventForm, SportTypeForm, VenueForm
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
        .exclude(kind=Competition.Kind.CULTURAL)
        .order_by('-start_date', '-id')
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

    base = Match.objects.filter(
        event__competition__in=competitions,
    ).select_related(
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

    all_events = [event for row in competition_rows for event in row['events']]
    open_statuses = tuple(value for value in SportsEvent.Status.values if value not in ('COMPLETED', 'CANCELLED'))

    return render(request, 'sports/sports_hub.html', {
        'competition_rows': competition_rows,
        'stats': {
            'sport_types': SportType.objects.filter(is_active=True).count(),
            'venues': Venue.objects.filter(is_active=True).count(),
            'events': len(all_events),
            'events_open': sum(event.status in open_statuses for event in all_events),
            'events_done': sum(event.status == SportsEvent.Status.COMPLETED for event in all_events),
            'matches': base.count(),
            'completed': base.filter(status=Match.Status.COMPLETED).count(),
            'awaiting': base.filter(status=Match.Status.SCHEDULED).count(),
            'overdue': base.filter(status=Match.Status.SCHEDULED, scheduled_start__lt=now).count(),
        },
        'overdue': list(overdue),
        'upcoming': list(upcoming),
        'today': today,
    })


@management_required
def match_board(request):
    """Every match across every competition, filtered, split into the Sports and
    Socio Cultural categories and grouped by day."""
    matches = Match.objects.select_related(
        'event', 'event__competition', 'event__sport_type', 'venue',
    ).prefetch_related('entries__team', 'entries__participant')

    competition_id = request.GET.get('competition', '')
    sport_id = request.GET.get('sport', '')
    venue_id = request.GET.get('venue', '')
    status = request.GET.get('status', '')
    day = request.GET.get('day', '')
    category = request.GET.get('category', '')

    if competition_id.isdigit():
        matches = matches.filter(event__competition_id=int(competition_id))
    if sport_id.isdigit():
        matches = matches.filter(event__sport_type_id=int(sport_id))
    if venue_id.isdigit():
        matches = matches.filter(venue_id=int(venue_id))
    if status in Match.Status.values:
        matches = matches.filter(status=status)
    # Competitions flagged as cultural surface their bracket events under
    # "Socio Cultural"; everything else (sports and mixed) stays under Sports.
    if category == 'cultural':
        matches = matches.filter(event__competition__kind=Competition.Kind.CULTURAL)
    elif category == 'sports':
        matches = matches.exclude(event__competition__kind=Competition.Kind.CULTURAL)

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

    # Split each day's matches into the two display categories so the board
    # never mixes sports play with socio-cultural events in one table.
    def category_groups(day_matches):
        cultural = [
            match for match in day_matches
            if match.event.competition.kind == Competition.Kind.CULTURAL
        ]
        cultural_ids = {match.id for match in cultural}
        sports = [match for match in day_matches if match.id not in cultural_ids]
        return [
            {'key': 'sports', 'label': 'Sports', 'matches': sports},
            {'key': 'cultural', 'label': 'Socio Cultural', 'matches': cultural},
        ]

    sections = [
        {
            'day': day,
            'count': len(day_matches),
            'groups': category_groups(day_matches),
        }
        for day, day_matches in days.items()
    ]
    unscheduled_groups = category_groups(unscheduled)

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
        'category': category,
        'day': day,
    }
    active_count = sum(1 for value in filter_state.values() if value)

    competition_choices = Competition.objects.order_by('-start_date')
    if category == 'cultural':
        competition_choices = competition_choices.filter(
            kind=Competition.Kind.CULTURAL,
        )
    elif category == 'sports':
        competition_choices = competition_choices.exclude(
            kind=Competition.Kind.CULTURAL,
        )

    return render(request, 'sports/match_board.html', {
        'days': days,
        'sections': sections,
        'unscheduled': unscheduled,
        'unscheduled_groups': unscheduled_groups,
        'day_keys': day_keys,
        'selected_index': selected_index,
        'prev_day': prev_day,
        'next_day': next_day,
        'total': total,
        'active_count': active_count,
        'filter_state': filter_state,
        'competitions': competition_choices,
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
    if competition.kind == Competition.Kind.CULTURAL:
        messages.error(request, 'Sports events require a Sports competition.')
        return redirect('competition_detail', competition_id=competition.pk)
    defaults = {'GROUP_KNOCKOUT': 'GROUP_STAGE'}
    form = SportsEventForm(request.POST or None, initial={'format': defaults.get(competition.tournament_format, competition.tournament_format or 'SINGLE_ELIMINATION')})
    if request.method == 'POST' and form.is_valid():
        event = form.save(commit=False)
        event.competition = competition
        if not event.name.strip():
            event.name = f'{event.sport_type.name} - {event.get_gender_display()}'
        event.save()
        if competition.status == 'COMPLETED':
            competition.status = 'ACTIVE'
            competition.save(update_fields=['status'])
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
    matches = event.matches.select_related('venue').prefetch_related('entries__team', 'entries__participant').order_by('round_number', 'id')
    return render(request, 'sports/event_detail.html', {
        'event': event,
        'entries': entries,
        'matches': matches,
        'overview': match_overview(event),
        'entry_form': EventEntryForm(event=event),
        'bracket_generated': event.matches.exists(),
        'can_clear_bracket': not event.confirmed_at and not event.matches.filter(status='COMPLETED', entries__score__isnull=False).exists(),
        **_workflow_context(event),
    })


@management_required
@require_POST
@transaction.atomic
def add_event_entry(request, event_id):
    event = get_object_or_404(SportsEvent.objects.select_for_update(), id=event_id)
    if event.matches.exists() or event.status in ('COMPLETED', 'CANCELLED'):
        messages.error(request, 'Entries are locked after fixtures are generated. Clear unplayed fixtures before changing entries.')
        return redirect('sport_event_detail', event_id=event.pk)

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
@transaction.atomic
def update_entry_status(request, event_id, entry_id):
    event = get_object_or_404(SportsEvent.objects.select_for_update(), id=event_id)
    if event.matches.exists() or event.status in ('COMPLETED', 'CANCELLED'):
        messages.error(request, 'Entries are locked after fixtures are generated. Clear unplayed fixtures before changing entries.')
        return redirect('sport_event_detail', event_id=event.pk)

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
@transaction.atomic
def remove_event_entry(request, event_id, entry_id):
    event = get_object_or_404(SportsEvent.objects.select_for_update(), id=event_id)
    if event.matches.exists() or event.status in ('COMPLETED', 'CANCELLED'):
        messages.error(request, 'Entries are locked after fixtures are generated. Clear unplayed fixtures before changing entries.')
        return redirect('sport_event_detail', event_id=event.pk)

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
    try:
        delete_bracket(event)
    except ValueError as error:
        messages.error(request, str(error))
        return redirect('sport_event_detail', event_id=event.pk)
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
    matches = event.matches.select_related('venue').prefetch_related('entries__team', 'entries__participant').order_by('round_number', 'id')
    from sms.services import is_configured
    return render(request, 'sports/match_schedule.html', {
        'event': event,
        'matches': matches,
        'sms_configured': is_configured(),
    })


@management_required
@transaction.atomic
def create_match(request, event_id):
    event = get_object_or_404(SportsEvent.objects.select_for_update(), id=event_id)
    match = Match(event=event, venue=event.venue)
    form = ManualMatchForm(request.POST if request.method == 'POST' else None, instance=match)
    if request.method == 'POST' and form.is_valid():
        match = form.save()
        record_action_from_request(request, 'MATCH_CREATED', target=match,
                                   details=f'Manual match created: {match.contestants_display()}')
        messages.success(request, 'Manual match and opponents created.')
        return redirect('match_schedule', event_id=event.id)
    return render(request, 'sports/match_form.html', {
        'form': form, 'match': match, 'creating': True, 'sms_configured': False,
    })


def _ensure_default_sport_event(competition):
    """Return an open SportsEvent for a Sports competition, creating one if none exists yet."""
    existing = (
        competition.sport_events
        .filter(confirmed_at__isnull=True)
        .exclude(status__in=[SportsEvent.Status.COMPLETED, SportsEvent.Status.CANCELLED])
        .first()
    )
    if existing:
        return existing

    sport_type = SportType.objects.filter(is_active=True, name__iexact=competition.name.strip()).first()
    if sport_type is None:
        sport_type, _ = SportType.objects.get_or_create(
            name=competition.name.strip()[:100] or 'General Sport',
            defaults={'team_based': True, 'is_active': True},
        )

    format_map = {
        Competition.TournamentFormat.SINGLE_ELIMINATION: SportsEvent.Format.SINGLE_ELIMINATION,
        Competition.TournamentFormat.DOUBLE_ELIMINATION: SportsEvent.Format.DOUBLE_ELIMINATION,
        Competition.TournamentFormat.ROUND_ROBIN: SportsEvent.Format.ROUND_ROBIN,
        Competition.TournamentFormat.GROUP_KNOCKOUT: SportsEvent.Format.GROUP_STAGE,
        Competition.TournamentFormat.BEST_OF: SportsEvent.Format.BEST_OF,
        Competition.TournamentFormat.LEAGUE: SportsEvent.Format.LEAGUE,
    }
    event_format = format_map.get(competition.tournament_format, SportsEvent.Format.SINGLE_ELIMINATION)

    return SportsEvent.objects.create(
        competition=competition,
        sport_type=sport_type,
        name=competition.name,
        team_based=sport_type.team_based,
        format=event_format,
        status=SportsEvent.Status.SCHEDULED,
    )


@management_required
@transaction.atomic
def create_board_match(request):
    """Single-page Match Board workflow: pick an event or sports competition,
    choose Team 1 vs Team 2 directly, and schedule the match with zero redirects."""
    open_events = list(
        SportsEvent.objects
        .filter(confirmed_at__isnull=True)
        .exclude(status__in=[SportsEvent.Status.COMPLETED, SportsEvent.Status.CANCELLED])
        .select_related('competition', 'sport_type', 'venue')
        .order_by('competition__name', 'name')
    )
    event_comp_ids = {ev.competition_id for ev in open_events}
    sports_comps_without_events = list(
        Competition.objects
        .filter(status='ACTIVE')
        .exclude(kind=Competition.Kind.CULTURAL)
        .exclude(id__in=event_comp_ids)
        .order_by('-id')
    )

    target_options = [
        {
            'value': f'event:{ev.id}',
            'label': f'{ev.name} — {ev.competition.name} ({ev.sport_type.name})',
            'event': ev,
            'competition': ev.competition,
        }
        for ev in open_events
    ] + [
        {
            'value': f'comp:{comp.id}',
            'label': f'{comp.name} (Sports competition)',
            'event': None,
            'competition': comp,
        }
        for comp in sports_comps_without_events
    ]

    raw_target = (
        request.POST.get('event') if request.method == 'POST' else request.GET.get('event')
    ) or ''
    raw_competition_id = request.GET.get('competition', '')

    selected_option = None
    if raw_target:
        if raw_target.isdigit():
            selected_option = next(
                (opt for opt in target_options if opt['event'] and opt['event'].id == int(raw_target)),
                None,
            )
        else:
            selected_option = next((opt for opt in target_options if opt['value'] == raw_target), None)

    if selected_option is None and request.method != 'POST' and target_options:
        if raw_competition_id.isdigit():
            selected_option = next(
                (opt for opt in target_options if opt['competition'].id == int(raw_competition_id)),
                None,
            )
        if selected_option is None:
            selected_option = target_options[0]

    selected_event = selected_option['event'] if selected_option else None
    selected_competition = selected_option['competition'] if selected_option else None

    form = None
    if selected_option is not None:
        if selected_event is not None:
            selected_event = SportsEvent.objects.select_for_update().select_related(
                'competition', 'sport_type', 'venue',
            ).get(pk=selected_event.pk)
        form = BoardManualMatchForm(
            request.POST if request.method == 'POST' else None,
            event=selected_event,
            team_based=selected_event.team_based if selected_event else True,
        )
        if request.method == 'POST' and form.is_valid():
            target_event = selected_event or _ensure_default_sport_event(selected_competition)
            match = form.save(event=target_event)
            record_action_from_request(
                request,
                'MATCH_CREATED',
                target=match,
                details=f'Manual match created from match board: {match.contestants_display()}',
            )
            messages.success(request, f'Match created: {match.contestants_display()}.')
            return redirect('match_board')
    elif request.method == 'POST':
        messages.error(request, 'Select a sport event or competition to create a match.')

    return render(request, 'sports/board_match_form.html', {
        'target_options': target_options,
        'selected_option': selected_option,
        'selected_event': selected_event,
        'selected_competition': selected_competition,
        'form': form,
    })


def _safe_board_redirect(request):
    next_url = (request.POST.get('next') or '').strip()
    if next_url and url_has_allowed_host_and_scheme(
        next_url,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return redirect(next_url)
    return redirect('match_board')


@management_required
@require_POST
@transaction.atomic
def delete_match(request, match_id):
    match = get_object_or_404(Match.objects.select_related('event'), id=match_id)
    contestants = match.contestants_display()
    summary = f'{match.event.name} - {match.label} ({contestants})'
    match.delete()
    record_action_from_request(
        request,
        'MATCH_DELETED',
        details=f'Deleted match from match board: {summary}',
    )
    messages.success(request, f'Deleted match: {summary}.')
    return _safe_board_redirect(request)


@management_required
@require_POST
@transaction.atomic
def bulk_delete_matches(request):
    raw_ids = request.POST.getlist('match_ids')
    match_ids = [int(mid) for mid in raw_ids if str(mid).isdigit()]
    if not match_ids:
        messages.warning(request, 'Select at least one match to delete.')
        return _safe_board_redirect(request)

    matches = list(Match.objects.filter(id__in=match_ids).select_related('event'))
    if not matches:
        messages.warning(request, 'No matching matches were found to delete.')
        return _safe_board_redirect(request)

    deleted_ids = [match.id for match in matches]
    labels = [f'{match.event.name} - {match.label}' for match in matches]
    Match.objects.filter(id__in=deleted_ids).delete()

    preview = ', '.join(labels[:10]) + (' ...' if len(labels) > 10 else '')
    record_action_from_request(
        request,
        'MATCH_BULK_DELETED',
        details=f'Bulk deleted {len(deleted_ids)} match(es): {preview}',
    )
    messages.success(request, f'Successfully deleted {len(deleted_ids)} match(es).')
    return _safe_board_redirect(request)


@management_required
@transaction.atomic
def edit_match(request, match_id):
    match = get_object_or_404(Match.objects.select_related('event__competition'), id=match_id)
    # Serialize manual edits to matches belonging to the same event.
    match.event = SportsEvent.objects.select_for_update().get(pk=match.event_id)
    match = Match.objects.select_for_update().select_related('event__competition').get(pk=match.pk)
    previous = {
        'scheduled_start': match.scheduled_start,
        'scheduled_end': match.scheduled_end,
        'venue_id': match.venue_id,
        'status': match.status,
    }
    form = ManualMatchForm(request.POST if request.method == 'POST' else None, instance=match)
    if request.method == 'POST' and form.is_valid():
        match = form.save()
        record_action_from_request(request, 'MATCH_UPDATED', target=match,
                                   details=f'Manual schedule/pairing update: {match.contestants_display()}')
        if request.POST.get('notify_sms') == 'on':
            kind = None
            if previous['status'] != match.status:
                kind = {
                    Match.Status.ONGOING: 'start',
                    Match.Status.POSTPONED: 'postponed',
                    Match.Status.CANCELLED: 'cancelled',
                }.get(match.status)
            if kind is None and (
                previous['scheduled_start'] != match.scheduled_start
                or previous['scheduled_end'] != match.scheduled_end
                or previous['venue_id'] != match.venue_id
            ):
                kind = 'rescheduled' if previous['scheduled_start'] else 'scheduled'
            if kind:
                from sms.services import describe_summary, notify_match
                summary = notify_match(match, kind, created_by=request.user)
                level = messages.SUCCESS if summary['sent'] else messages.WARNING
                messages.add_message(request, level, describe_summary(summary))
        messages.success(request, 'Match schedule and pairing saved.')
        return redirect('match_schedule', event_id=match.event_id)

    from sms.services import is_configured
    return render(request, 'sports/match_form.html', {
        'form': form,
        'match': match,
        'sms_configured': is_configured(),
    })


@management_required
@require_POST
def record_match_result_view(request, match_id):
    match = get_object_or_404(Match.objects.select_related('event'), id=match_id)
    scores = {
        1: request.POST.get('score_1'),
        2: request.POST.get('score_2'),
    }
    wants_json = request.POST.get('format') == 'json'
    sms_summary = None
    try:
        record_match_result(match, scores, notes=request.POST.get('notes', ''), forfeited_side=int(request.POST['forfeited_side']) if request.POST.get('forfeited_side') else None)
        record_action_from_request(
            request,
            'MATCH_RESULT',
            target=match,
            details=f'Result recorded for {match.event.name} - {match.label}',
        )
        if request.POST.get('notify_sms') == 'on':
            from sms.services import describe_summary, notify_match
            sms_summary = notify_match(match, 'result', created_by=request.user)
            if not wants_json:
                level = messages.SUCCESS if sms_summary['sent'] else messages.WARNING
                messages.add_message(request, level, describe_summary(sms_summary))
        if wants_json:
            payload = {'ok': True, 'bracket': bracket_payload(match.event)}
            if sms_summary is not None:
                payload['sms'] = describe_summary(sms_summary)
            return JsonResponse(payload)
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
        'group': match.group,
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


def _knockout_preview(event):
    """Draw qualifier paths before qualification, without creating match records."""
    import math
    from .services import _seed_order
    groups = list(event.matches.exclude(group__isnull=True).values_list('group', flat=True).distinct().order_by('group'))
    if not groups:
        return None
    qualifiers = [f'Group {group} — #{position}' for group in groups for position in range(1, event.qualifiers_per_group + 1)]
    if len(qualifiers) < 2:
        return None
    size = 2 ** math.ceil(math.log2(len(qualifiers)))
    seed_order = _seed_order(size)
    rounds = []
    for round_index in range(int(math.log2(size))):
        count = size // 2 ** (round_index + 1)
        matches = []
        for index in range(count):
            names = []
            if round_index == 0:
                for seed in seed_order[index * 2:index * 2 + 2]:
                    names.append(qualifiers[seed - 1] if seed <= len(qualifiers) else 'Bye')
            else:
                names = [f'Winner of {rounds[-1]["label"]} {index * 2 + side}' for side in (1, 2)]
            matches.append({
                'id': f'preview-{round_index}-{index}',
                'label': f'{ROUND_LABELS.get(count * 2, "Round")} {index + 1}',
                'status': 'PENDING', 'statusDisplay': 'Awaiting qualifiers',
                'next': f'preview-{round_index + 1}-{index // 2}' if count > 1 else None,
                'recordUrl': None, 'entries': [], 'placeholder_names': names,
                'venue': None, 'start': None,
            })
        rounds.append({'label': ROUND_LABELS.get(count * 2, f'Round of {count * 2}'), 'done': 0, 'total': count, 'matches': matches})
    return {'rounds': rounds, 'champion': None, 'preview': True}


def _live_event_schedule(event, now=None):
    """Choose a real current/next fixture; completed and postponed slots never occupy it."""
    now = now or timezone.now()
    matches = list(event.matches.select_related('venue').prefetch_related('entries__team', 'entries__participant'))
    def order(match):
        return (match.scheduled_start is None, match.scheduled_start or now, match.round_number, match.pk)
    eligible = [m for m in matches if m.status in ('ONGOING', 'SCHEDULED') and m.entries.count() == 2]
    ongoing = sorted([m for m in eligible if m.status == 'ONGOING'], key=order)
    due = sorted([m for m in eligible if m.status == 'SCHEDULED' and m.scheduled_start and m.scheduled_start <= now], key=order)
    future = sorted([m for m in eligible if m.status == 'SCHEDULED' and m.scheduled_start and m.scheduled_start > now], key=order)
    current = (ongoing or due or [None])[0]
    next_match = next((m for m in due + future if not current or m.pk != current.pk), None)
    state = 'ongoing' if ongoing else 'due' if due else 'upcoming' if future else 'waiting'
    if event.status == 'CANCELLED':
        state, current, next_match = 'cancelled', None, None
    elif matches and all(m.status in ('COMPLETED', 'CANCELLED') for m in matches):
        state, current, next_match = 'finished', None, None
    def brief(match):
        if not match:
            return None
        result = _bracket_match_brief(match)
        result['scheduled_start'] = match.scheduled_start.isoformat() if match.scheduled_start else None
        result['scheduled_end'] = match.scheduled_end.isoformat() if match.scheduled_end else None
        return result
    return {'state': state, 'current': brief(current), 'next': brief(next_match),
            'parallel_count': max(0, len(ongoing) - 1),
            'schedule_url': reverse('match_schedule', args=[event.pk])}


def bracket_payload(event):
    payload = _bracket_payload(event)
    if payload is not None:
        # Reload status because result recording may have just changed the event.
        current_event = SportsEvent.objects.get(pk=event.pk)
        payload['schedule'] = _live_event_schedule(current_event)
        payload['event'] = {'id': current_event.pk, 'name': current_event.name, 'format': current_event.get_format_display(), 'competition': current_event.competition.name, 'bracket_url': reverse('event_bracket', args=[current_event.pk]), 'schedule_url': reverse('match_schedule', args=[current_event.pk]), 'standings_url': reverse('event_standings', args=[current_event.pk]), 'detail_url': reverse('sport_event_detail', args=[current_event.pk])}
    return payload


def _bracket_payload(event):
    """Format-aware interactive fixtures, series, or elimination graph."""
    matches = list(event.matches.select_related('venue', 'next_match').prefetch_related('entries__team', 'entries__participant').order_by('round_number', 'id'))
    if not matches:
        return None
    mode = 'elimination'
    if event.format == SportsEvent.Format.BEST_OF:
        mode = 'series'
    elif event.format == SportsEvent.Format.ROUND_ROBIN or (event.format == SportsEvent.Format.LEAGUE and not any(m.group is None for m in matches)):
        mode = 'fixtures'
    elif event.format == SportsEvent.Format.LEAGUE and not event.playoff_count:
        mode = 'fixtures'
    elif event.format == SportsEvent.Format.DOUBLE_ELIMINATION:
        mode = 'double'
    by_round = OrderedDict()
    for match in matches:
        if match.name == 'Bronze Match' or (mode in ('elimination', 'double') and match.group):
            continue
        by_round.setdefault(match.round_number, []).append(match)
    if not by_round:
        payload = _knockout_preview(event) if event.format == SportsEvent.Format.GROUP_STAGE else None
        if payload:
            payload.update(mode='elimination', group_matches=[_bracket_match_brief(m) for m in matches if m.group])
        return payload
    rounds = []
    for number, round_matches in by_round.items():
        if mode == 'double':
            label = round_matches[0].name.replace('WB Round', 'Winners round').replace('LB Round', 'Losers round')
        elif mode == 'series':
            label = f'Game {number}'
        elif mode == 'fixtures':
            label = f'Round {number}'
        else:
            label = ROUND_LABELS.get(2 * len(round_matches), f'Round of {2 * len(round_matches)}')
        rounds.append({'label': label, 'done': sum(m.status == 'COMPLETED' for m in round_matches), 'total': len(round_matches), 'matches': [_bracket_match_brief(m) for m in round_matches]})
    if mode == 'double':
        from .services import _double_elim_rounds
        k, _ = _double_elim_rounds(event)
        grand = next((m for m in matches if m.name == 'Grand Final'), None)
        reset = next((m for m in matches if m.name == 'Grand Final Reset'), None)
        for round_data in rounds:
            for brief in round_data['matches']:
                source = next(m for m in matches if m.pk == brief['id'])
                if source.name == 'Grand Final' and reset:
                    brief['next'] = reset.pk
                if not source.name.startswith('WB Round'):
                    continue
                r = source.round_number - 1
                peers = by_round[source.round_number]
                index = peers.index(source)
                if r == k - 1:
                    targets = [m for m in matches if m.name.startswith('LB Round') and m.round_number == 3 * k - 2]
                    target = targets[0] if targets else grand
                else:
                    targets = by_round.get(k + (1 if r == 0 else 2 * r), [])
                    slot = index // 2 if r == 0 else index
                    target = targets[slot] if slot < len(targets) else None
                brief['loserNext'] = target.pk if target else None
    champion = None
    if mode in ('elimination', 'double'):
        final = list(by_round.values())[-1]
        if len(final) == 1 and final[0].status == 'COMPLETED' and final[0].winner:
            champion = final[0].winner.display_name
    standings = []
    if mode in ('fixtures', 'series'):
        standings = [{key: row.get(key, 0) for key in ('rank', 'name', 'played', 'wins', 'draws', 'losses', 'total_points')} for row in compute_standings(event)]
        from .workflow import proposed_podium
        try:
            podium = proposed_podium(event)
            champion = podium[0][0].display_name if podium else None
        except ValueError:
            pass
    return {'rounds': rounds, 'champion': champion, 'mode': mode, 'standings': standings,
            'best_of': event.best_of, 'wins_required': event.best_of // 2 + 1,
            'extra_matches': [_bracket_match_brief(m) for m in matches if m.name == 'Bronze Match'],
            'group_matches': [_bracket_match_brief(m) for m in matches if m.group] if mode in ('elimination', 'double') else []}


def _scheduled_bracket_event(fallback, now=None):
    """Follow an ongoing fixture or a fixture whose scheduled time has arrived."""
    now = now or timezone.now()
    candidates = Match.objects.exclude(event__competition__kind=Competition.Kind.CULTURAL).exclude(
        event__status__in=['CANCELLED', 'COMPLETED'],
    ).annotate(contestants=Count('entries')).filter(contestants=2).select_related('event__competition')
    ongoing = candidates.filter(status='ONGOING').order_by('scheduled_start', 'pk')
    current = candidates.filter(status='SCHEDULED', scheduled_start__lte=now).filter(
        Q(scheduled_end__gt=now) | Q(scheduled_end__isnull=True, scheduled_start__date=timezone.localdate(now)),
    ).order_by('scheduled_start', 'pk')
    selected = list(ongoing) or list(current)
    # Keep a selected event stable when several courts are playing simultaneously.
    return next((m.event for m in selected if m.event_id == fallback.pk), selected[0].event if selected else fallback)


@management_required
def event_bracket(request, event_id):
    event = get_object_or_404(SportsEvent.objects.select_related('competition'), id=event_id)
    follow_schedule = request.GET.get('follow', '0' if request.GET.get('format') == 'json' else '1') == '1'
    if follow_schedule:
        event = _scheduled_bracket_event(event)
    bracket = bracket_payload(event)
    if request.GET.get('format') == 'json':
        response = JsonResponse(bracket or {'rounds': [], 'champion': None, 'schedule': _live_event_schedule(event)})
        response['Cache-Control'] = 'no-store'
        return response
    return render(request, 'sports/event_bracket.html', {
        'event': event,
        'bracket': bracket,
        'overview': match_overview(event),
        'groups': group_stage_overview(event)[0] if event.format == SportsEvent.Format.GROUP_STAGE else {},
        'follow_schedule': follow_schedule,
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

def _workflow_context(event):
    from .workflow import proposed_podium
    try:
        podium = proposed_podium(event)
        issue = ''
    except ValueError as error:
        podium, issue = [], str(error)
    return {'proposed_podium': podium, 'completion_issue': issue}


@management_required
@require_POST
def tournament_action(request, event_id):
    from .workflow import confirm_awards, reopen_event, resolve_ties, correct_result, seed_entries
    from accounts.access import get_user_role
    from django.core.exceptions import PermissionDenied
    if get_user_role(request.user) not in ('ADMINISTRATOR', 'SPORTS_COORDINATOR'):
        raise PermissionDenied('Only administrators and sports coordinators can confirm or correct sports results.')
    event = get_object_or_404(SportsEvent, pk=event_id)
    action = request.POST.get('action')
    try:
        if action == 'confirm':
            confirm_awards(event, request.user)
        elif action == 'reopen':
            reopen_event(event, request.user, request.POST.get('reason', ''))
        elif action == 'resolve':
            order = [int(x.strip()) for x in (request.POST.getlist('order[]') or request.POST.get('order', '').split(','))]
            resolve_ties(event, request.user, order, request.POST.get('reason', ''))
        elif action == 'seed':
            seed_entries(event, request.user, [int(x.strip()) for x in (request.POST.getlist('order[]') or request.POST.get('order', '').split(','))])
        elif action == 'correct':
            match = get_object_or_404(Match, pk=request.POST.get('match_id'), event=event)
            correct_result(match, request.user, {1: request.POST.get('score_1'), 2: request.POST.get('score_2')}, request.POST.get('reason', ''))
        else:
            raise ValueError('Unknown tournament action.')
        messages.success(request, 'Tournament updated successfully.')
    except (ValueError, TypeError) as error:
        messages.error(request, str(error))
    return redirect('sport_event_detail', event_id=event.pk)
