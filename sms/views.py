from datetime import datetime, time, timedelta
from urllib.parse import urlencode

from django.contrib import messages
from django.db.models import Case, Count, IntegerField, Max, Q, Value, When
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from accounts.access import management_required
from competitions.models import Competition, Round
from sports.models import Match, SportsEvent

from .models import SmsMessage
from .services import (
    CULTURAL_KIND_CHOICES,
    NOTIFY_KIND_CHOICES,
    NOTIFY_KIND_LABELS,
    describe_summary,
    get_config,
    is_configured,
    notify_match,
    notify_matches,
    notify_round,
    notify_rounds,
)

# One click walks the gateway once per session (a match or a cultural round), so
# very wide schedules are notified per event instead of per competition.
MAX_BULK_MATCHES = 40
SCOPES = ('upcoming', 'today', 'all')


def _selected_scope(request):
    scope = (request.GET.get('scope') or request.POST.get('scope') or 'upcoming')
    scope = scope.strip().lower()
    return scope if scope in SCOPES else 'upcoming'


def _scope_filter(queryset, scope, now=None):
    """Limit a match queryset to the schedule window picked on the page."""
    if scope == 'today':
        return queryset.filter(scheduled_start__date=timezone.localdate())
    if scope == 'upcoming':
        now = now or timezone.now()
        return queryset.filter(Q(scheduled_start__gte=now) | Q(scheduled_start__isnull=True))
    return queryset


def _matches_queryset():
    return (
        Match.objects
        .select_related('event', 'event__competition', 'event__sport_type', 'venue')
        .prefetch_related('entries__team', 'entries__participant')
    )


def _rounds_queryset():
    """Socio-cultural sessions: rounds carry no clock, the competition does."""
    return (
        Round.objects
        .select_related('competition')
        .filter(competition__kind=Competition.Kind.CULTURAL)
        .annotate(
            contestant_total=Count('competition__participants', distinct=True),
        )
    )


def _round_scope(queryset, scope, now=None):
    """Limit a round queryset with the same window picked for the matches."""
    now = now or timezone.now()
    if scope == 'today':
        start_of_day = timezone.make_aware(
            datetime.combine(timezone.localdate(), time.min),
        )
        return queryset.filter(
            competition__start_date__lt=start_of_day + timedelta(days=1),
            competition__end_date__gte=start_of_day,
        )
    if scope == 'upcoming':
        return queryset.filter(competition__end_date__gte=now)
    return queryset


def _positive_int(value):
    try:
        number = int(str(value).strip())
    except (TypeError, ValueError):
        return None
    return number if number > 0 else None


def _suggested_kind(match):
    """Update type that fits the match status, used to preselect the picker."""
    return {
        Match.Status.COMPLETED: 'result',
        Match.Status.ONGOING: 'live',
        Match.Status.POSTPONED: 'postponed',
        Match.Status.CANCELLED: 'cancelled',
    }.get(match.status, 'scheduled')


def _suggested_round_kind(round_obj):
    return {
        'COMPLETED': 'result',
        'ONGOING': 'live',
    }.get(round_obj.status, 'scheduled')


def _safe_next(request):
    """Same-page redirect target sent by the forms, when it is trustworthy."""
    target = request.POST.get('next') or ''
    if target and url_has_allowed_host_and_scheme(
        target,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return target
    return ''


def _dashboard_url(scope='upcoming', competition_id=None):
    params = {'scope': scope}
    if competition_id:
        params['competition'] = competition_id
    return f"{reverse('sms_dashboard')}?{urlencode(params)}"


def _build_groups(rows, last_sent):
    """Nest prepared matches into competition -> event -> match rows."""
    competitions = []
    competition_index = {}
    event_index = {}

    for row in rows:
        match = row['match']
        event = match.event
        competition = event.competition

        competition_group = competition_index.get(competition.id)
        if competition_group is None:
            competition_group = {
                'competition': competition,
                'status': competition.status,
                'events': [],
                'match_total': 0,
                'event_total': 0,
            }
            competition_index[competition.id] = competition_group
            competitions.append(competition_group)

        event_group = event_index.get(event.id)
        if event_group is None:
            event_group = {'event': event, 'rows': [], 'match_total': 0}
            event_index[event.id] = event_group
            competition_group['events'].append(event_group)
            competition_group['event_total'] += 1

        event_group['rows'].append({**row, 'last_sent': last_sent.get(match.id)})
        event_group['match_total'] += 1
        competition_group['match_total'] += 1

    for competition_group in competitions:
        competition_group['bulk_allowed'] = (
            competition_group['match_total'] <= MAX_BULK_MATCHES
        )
    return competitions


def _build_cultural_groups(rows, last_sent):
    """Nest prepared rounds into one card per socio-cultural competition."""
    groups = []
    group_index = {}

    for row in rows:
        round_obj = row['round']
        competition = round_obj.competition
        group = group_index.get(competition.id)
        if group is None:
            group = {
                'competition': competition,
                'status': competition.status,
                'event_type': competition.get_cultural_event_type_display(),
                'rounds': [],
                'round_total': 0,
                'contestant_total': round_obj.contestant_total,
            }
            group_index[competition.id] = group
            groups.append(group)

        group['rounds'].append({**row, 'last_sent': last_sent.get(round_obj.id)})
        group['round_total'] += 1

    for group in groups:
        group['bulk_allowed'] = group['round_total'] <= MAX_BULK_MATCHES
    return groups


@management_required
def sms_dashboard(request):
    now = timezone.now()
    scope = _selected_scope(request)

    all_matches = Match.objects.all()
    all_rounds = _rounds_queryset()
    scope_options = [
        {
            'value': value,
            'label': label,
            'count': (
                _scope_filter(all_matches, value, now).count()
                + _round_scope(all_rounds, value, now).count()
            ),
        }
        for value, label in (('upcoming', 'Upcoming'), ('today', 'Today'), ('all', 'All'))
    ]

    sports_options = [
        {'id': row['id'], 'label': row['name'], 'count': row['total'], 'kind': 'SPORTS'}
        for row in (
            Competition.objects
            .exclude(kind=Competition.Kind.CULTURAL)
            .filter(sport_events__matches__isnull=False)
            .annotate(total=Count('sport_events__matches', distinct=True))
            .order_by('name')
            .values('id', 'name', 'total')
        )
    ]
    cultural_options = [
        {'id': row['id'], 'label': row['name'], 'count': row['total'], 'kind': 'CULTURAL'}
        for row in (
            Competition.objects
            .filter(kind=Competition.Kind.CULTURAL, rounds__isnull=False)
            .annotate(total=Count('rounds', distinct=True))
            .order_by('name')
            .values('id', 'name', 'total')
        )
    ]
    competition_options = sorted(
        sports_options + cultural_options,
        key=lambda option: option['label'].upper(),
    )
    allowed_ids = {option['id'] for option in competition_options}
    selected_competition = _positive_int(request.GET.get('competition'))
    if selected_competition not in allowed_ids:
        selected_competition = None

    matches = _scope_filter(_matches_queryset(), scope, now)
    rounds = _round_scope(all_rounds, scope, now)
    if selected_competition:
        matches = matches.filter(event__competition_id=selected_competition)
        rounds = rounds.filter(competition_id=selected_competition)
    matches = (
        matches
        .annotate(
            undated=Case(
                When(scheduled_start__isnull=True, then=Value(1)),
                default=Value(0),
                output_field=IntegerField(),
            ),
        )
        .order_by(
            'event__competition__name', 'event__name', 'undated',
            'scheduled_start', 'round_number', 'id',
        )
    )
    rounds = rounds.order_by('competition__name', 'order', 'id')

    rows = [{'match': match, 'suggested': _suggested_kind(match)} for match in matches]
    round_rows = [
        {'round': round_obj, 'suggested': _suggested_round_kind(round_obj)}
        for round_obj in rounds
    ]

    # One extra query so the page can show which schedules were texted already.
    match_ids = [row['match'].id for row in rows]
    round_ids = [row['round'].id for row in round_rows]
    last_match_sent, last_round_sent = {}, {}
    for entry in (
        SmsMessage.objects
        .exclude(status=SmsMessage.Status.FAILED)
        .filter(Q(match_id__in=match_ids) | Q(round_id__in=round_ids))
        .values('match_id', 'round_id')
        .annotate(latest=Max('created_at'))
    ):
        if entry['match_id']:
            last_match_sent[entry['match_id']] = entry['latest']
        elif entry['round_id']:
            last_round_sent[entry['round_id']] = entry['latest']

    groups = _build_groups(rows, last_match_sent)
    cultural_groups = _build_cultural_groups(round_rows, last_round_sent)

    category = request.GET.get('category', '')
    status = request.GET.get('status', '')
    log_queryset = SmsMessage.objects.select_related(
        'match__event', 'round__competition', 'created_by',
    )
    if category in SmsMessage.Category.values:
        log_queryset = log_queryset.filter(category=category)
    if status in SmsMessage.Status.values:
        log_queryset = log_queryset.filter(status=status)

    config = get_config()
    return render(request, 'sms/dashboard.html', {
        'groups': groups,
        'cultural_groups': cultural_groups,
        'row_total': len(rows) + len(round_rows),
        'scope': scope,
        'scope_options': scope_options,
        'competition_options': competition_options,
        'selected_competition': selected_competition,
        'selected_competition_label': next(
            (
                option['label']
                for option in competition_options
                if option['id'] == selected_competition
            ),
            '',
        ),
        'is_filtered': bool(selected_competition) or scope != 'upcoming',
        'max_bulk': MAX_BULK_MATCHES,
        'kind_choices': NOTIFY_KIND_CHOICES,
        'cultural_kind_choices': CULTURAL_KIND_CHOICES,
        'messages_list': log_queryset[:100],
        'categories': SmsMessage.Category.choices,
        'statuses': SmsMessage.Status.choices,
        'filter_category': category,
        'filter_status': status,
        'configured': is_configured(),
        'enabled': config['enabled'],
        'dry_run': config['dry_run'],
    })


@management_required
@require_POST
def sms_bulk_notify(request):
    """Text the same update type for every session currently shown for a
    competition (matches or socio-cultural rounds) or a single event."""
    back = _safe_next(request)

    kind = (request.POST.get('kind') or '').strip()
    if kind not in NOTIFY_KIND_LABELS:
        messages.error(request, 'Choose a valid SMS update type.')
        return redirect(back or _dashboard_url(_selected_scope(request)))

    scope = _selected_scope(request)
    label = NOTIFY_KIND_LABELS[kind]
    competition_id = _positive_int(request.POST.get('competition_id'))
    event_id = _positive_int(request.POST.get('event_id'))
    cultural = False

    if event_id:
        event = get_object_or_404(
            SportsEvent.objects.select_related('competition'), id=event_id,
        )
        sessions = _scope_filter(_matches_queryset().filter(event=event), scope)
        scope_label = event.name
        competition_id = competition_id or event.competition_id
    elif competition_id:
        competition = get_object_or_404(Competition, id=competition_id)
        scope_label = competition.name
        cultural = competition.kind == Competition.Kind.CULTURAL
        if cultural:
            sessions = _round_scope(
                _rounds_queryset().filter(competition=competition), scope,
            )
        else:
            sessions = _scope_filter(
                _matches_queryset().filter(event__competition=competition), scope,
            )
    else:
        messages.error(request, 'Pick a competition or an event to notify.')
        return redirect(back or _dashboard_url(scope))

    plural = 'rounds' if cultural else 'matches'
    back = back or _dashboard_url(scope, competition_id)
    total = sessions.count()
    if not total:
        messages.warning(
            request,
            f'No {scope_label} {plural} in this view, so nothing was texted. '
            'Switch to “All” to include finished schedules.',
        )
        return redirect(back)
    if total > MAX_BULK_MATCHES:
        messages.error(
            request,
            f'{total} {plural} is more than one bulk send can carry '
            f'({MAX_BULK_MATCHES}). Text the {plural} one at a time, or narrow '
            'the view to Today.',
        )
        return redirect(back)

    if cultural:
        summary = notify_rounds(sessions, kind, created_by=request.user)
    else:
        summary = notify_matches(sessions, kind, created_by=request.user)
    level = messages.SUCCESS if summary['sent'] else messages.WARNING
    messages.add_message(request, level, f'{label} \u2013 {scope_label}: {describe_summary(summary)}')
    return redirect(back)


@management_required
@require_POST
def sms_notify_match(request, match_id):
    match = get_object_or_404(
        Match.objects.select_related('event', 'event__competition', 'venue'),
        id=match_id,
    )
    kind = (request.POST.get('kind') or '').strip()
    schedule_url = reverse('match_schedule', kwargs={'event_id': match.event_id})
    if kind not in NOTIFY_KIND_LABELS:
        messages.error(request, 'Choose a valid SMS update type.')
        return redirect(_safe_next(request) or schedule_url)

    summary = notify_match(match, kind, created_by=request.user)
    level = messages.SUCCESS if summary['sent'] else messages.WARNING
    label = NOTIFY_KIND_LABELS[kind]
    messages.add_message(
        request,
        level,
        f'{label} \u2013 {match.event.name} ({match.label}): {describe_summary(summary)}',
    )
    return redirect(_safe_next(request) or schedule_url)


@management_required
@require_POST
def sms_notify_round(request, round_id):
    """Text every registered contestant of one socio-cultural round."""
    round_obj = get_object_or_404(
        Round.objects.select_related('competition'), id=round_id,
    )
    kind = (request.POST.get('kind') or '').strip()
    rounds_url = reverse('manage_rounds', kwargs={'competition_id': round_obj.competition_id})
    if kind not in NOTIFY_KIND_LABELS:
        messages.error(request, 'Choose a valid SMS update type.')
        return redirect(_safe_next(request) or rounds_url)

    summary = notify_round(round_obj, kind, created_by=request.user)
    level = messages.SUCCESS if summary['sent'] else messages.WARNING
    label = NOTIFY_KIND_LABELS[kind]
    messages.add_message(
        request,
        level,
        f'{label} \u2013 {round_obj.competition.name} ({round_obj.name}): '
        f'{describe_summary(summary)}',
    )
    return redirect(_safe_next(request) or rounds_url)
