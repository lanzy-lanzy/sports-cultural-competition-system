"""Semaphore SMS integration.

Semaphore's v4 API accepts a form-encoded POST to
``https://api.semaphore.co/api/v4/messages`` with ``apikey``, ``number``,
``message`` and an optional ``sendername``. Up to 1,000 numbers can be sent in
one call, which is the recommended way to notify a group.

The API key and sender name live in ``.env`` (see ``.env.example``); they are
never stored in the database. Every send is mirrored to :class:`SmsMessage` so
organizers can see what was delivered, to whom, and why something failed.
"""

from __future__ import annotations

import json
import re
from urllib import error, parse, request
from zoneinfo import ZoneInfo

from django.conf import settings
from django.core.cache import cache
from django.utils import timezone

from registrations.models import EventRegistration

from .models import SmsMessage

BALANCE_CACHE_KEY = 'sms:semaphore:account'
BALANCE_CACHE_SECONDS = 300
MAX_BULK_RECIPIENTS = 1000


class SmsError(Exception):
    """Raised when Semaphore cannot be reached or rejects a request."""


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

def get_config():
    return {
        'api_key': getattr(settings, 'SEMAPHORE_API_KEY', '') or '',
        'sender_name': getattr(settings, 'SEMAPHORE_SENDER_NAME', '') or '',
        'enabled': bool(getattr(settings, 'SEMAPHORE_ENABLED', True)),
        'dry_run': bool(getattr(settings, 'SEMAPHORE_DRY_RUN', False)),
        'timezone': getattr(settings, 'SEMAPHORE_TIMEZONE', 'Asia/Manila'),
    }


def is_configured():
    config = get_config()
    return bool(config['enabled'] and config['api_key'])


def masked_api_key():
    key = get_config()['api_key']
    if not key:
        return ''
    if len(key) <= 4:
        return '*' * len(key)
    return f'{"*" * (len(key) - 4)}{key[-4:]}'


# ---------------------------------------------------------------------------
# Phone numbers
# ---------------------------------------------------------------------------

def normalize_phone_number(value):
    """Return a PH mobile number as ``09XXXXXXXXX`` or ``''`` when invalid.

    Accepts ``09171234567``, ``+63 917 123 4567``, ``639171234567`` and
    ``9171234567``. Semaphore only delivers to Philippine mobile numbers.
    """
    if value is None:
        return ''
    digits = re.sub(r'\D', '', str(value))
    if not digits:
        return ''
    if digits.startswith('00'):
        digits = digits[2:]
    if digits.startswith('63') and len(digits) == 12:
        digits = '0' + digits[2:]
    elif digits.startswith('9') and len(digits) == 10:
        digits = '0' + digits
    if len(digits) == 11 and digits.startswith('09'):
        return digits
    return ''


# ---------------------------------------------------------------------------
# HTTP
# ---------------------------------------------------------------------------

def _post(path, payload):
    data = parse.urlencode(payload).encode('utf-8')
    http_request = request.Request(
        path,
        data=data,
        headers={
            'Accept': 'application/json',
            'Content-Type': 'application/x-www-form-urlencoded',
        },
        method='POST',
    )
    try:
        with request.urlopen(http_request, timeout=int(settings.SEMAPHORE_TIMEOUT)) as response:
            body = response.read().decode('utf-8', errors='replace')
    except error.HTTPError as exc:
        detail = ''
        try:
            detail = exc.read().decode('utf-8', errors='replace')
        except Exception:  # pragma: no cover - defensive
            pass
        message = _extract_error(detail) or f'Semaphore returned HTTP {exc.code}.'
        raise SmsError(message) from exc
    except error.URLError as exc:
        raise SmsError(f'Could not reach Semaphore: {exc.reason}') from exc
    except Exception as exc:  # pragma: no cover - network edge cases
        raise SmsError(f'SMS request failed: {exc}') from exc

    if not body.strip():
        return []
    try:
        return json.loads(body)
    except json.JSONDecodeError as exc:
        raise SmsError('Semaphore returned an unreadable response.') from exc


def _extract_error(raw):
    if not raw:
        return ''
    try:
        data = json.loads(raw) if isinstance(raw, str) else raw
    except (TypeError, json.JSONDecodeError):
        return str(raw)[:300]
    if isinstance(data, dict):
        for key in ('message', 'error', 'errors', 'apikey'):
            value = data.get(key)
            if value:
                if isinstance(value, (list, tuple)):
                    return ', '.join(str(item) for item in value)[:300]
                if isinstance(value, dict):
                    return ', '.join(f'{k}: {v}' for k, v in value.items())[:300]
                return str(value)[:300]
    return str(data)[:300]


# ---------------------------------------------------------------------------
# Sending
# ---------------------------------------------------------------------------

def _empty_summary():
    config = get_config()
    return {
        'configured': is_configured(),
        'dry_run': config['dry_run'],
        'recipients': 0,
        'sent': 0,
        'failed': 0,
        'skipped': 0,
        'error': '',
        'detail': '',
    }


def _clean_message(body):
    body = (body or '').strip()
    # Semaphore silently drops messages that begin with the word "TEST".
    if body.upper().startswith('TEST'):
        body = f'[Competrack] {body}'
    return body


def send_bulk_sms(recipients, body, *, category=SmsMessage.Category.MANUAL,
                  match=None, round=None, created_by=None):
    """Send one message to many recipients through a single Semaphore call.

    ``recipients`` is an iterable of ``(phone, name)`` pairs. Invalid numbers
    are skipped. The returned summary contains counts suitable for a UI
    message, and each recipient gets an :class:`SmsMessage` row. Pass ``match``
    for a sports schedule or ``round`` for a socio-cultural session so the log
    stays traceable.
    """
    summary = _empty_summary()
    body = _clean_message(body)
    if not body:
        summary['error'] = 'The SMS message is empty.'
        return summary

    cleaned = {}
    for item in recipients or []:
        if isinstance(item, dict):
            phone, name = item.get('phone'), item.get('name', '')
        else:
            try:
                phone, name = item
            except (TypeError, ValueError):
                phone, name = item, ''
        normalized = normalize_phone_number(phone)
        if not normalized:
            summary['skipped'] += 1
            continue
        if normalized not in cleaned:
            cleaned[normalized] = (name or '').strip()

    summary['recipients'] = len(cleaned)
    if not cleaned:
        summary['detail'] = 'No valid PH mobile numbers were found for this message.'
        return summary

    config = get_config()
    if not summary['configured']:
        summary['skipped'] += len(cleaned)
        summary['detail'] = (
            'SMS is disabled or SEMAPHORE_API_KEY is missing. '
            'Add the key and sender name to .env, then restart the server.'
        )
        return summary

    numbers = list(cleaned)
    if config['dry_run']:
        for number in numbers:
            SmsMessage.objects.create(
                recipient=number,
                recipient_name=cleaned[number],
                body=body,
                sender_name=config['sender_name'],
                category=category,
                status=SmsMessage.Status.SKIPPED,
                provider_status='DRY_RUN',
                match=match,
                round=round,
                created_by=created_by,
            )
        summary['skipped'] = len(numbers)
        summary['detail'] = f'Dry run: {len(numbers)} SMS message(s) were logged but not sent.'
        return summary

    for start in range(0, len(numbers), MAX_BULK_RECIPIENTS):
        chunk = numbers[start:start + MAX_BULK_RECIPIENTS]
        payload = {
            'apikey': config['api_key'],
            'number': ','.join(chunk),
            'message': body,
        }
        if config['sender_name']:
            payload['sendername'] = config['sender_name']

        try:
            response = _post(settings.SEMAPHORE_API_URL, payload)
        except SmsError as exc:
            summary['failed'] += len(chunk)
            summary['error'] = str(exc)
            SmsMessage.objects.bulk_create([
                SmsMessage(
                    recipient=number,
                    recipient_name=cleaned[number],
                    body=body,
                    sender_name=config['sender_name'],
                    category=category,
                    status=SmsMessage.Status.FAILED,
                    error=str(exc),
                    match=match,
                    round=round,
                    created_by=created_by,
                )
                for number in chunk
            ])
            continue

        if isinstance(response, dict):
            summary['failed'] += len(chunk)
            summary['error'] = _extract_error(response) or 'Semaphore rejected the request.'
            SmsMessage.objects.bulk_create([
                SmsMessage(
                    recipient=number,
                    recipient_name=cleaned[number],
                    body=body,
                    sender_name=config['sender_name'],
                    category=category,
                    status=SmsMessage.Status.FAILED,
                    error=summary['error'],
                    match=match,
                    round=round,
                    created_by=created_by,
                )
                for number in chunk
            ])
            continue

        by_recipient = {}
        for entry in response or []:
            if not isinstance(entry, dict):
                continue
            normalized = normalize_phone_number(entry.get('recipient'))
            if normalized and normalized not in by_recipient:
                by_recipient[normalized] = entry

        logs = []
        for number in chunk:
            entry = by_recipient.get(number)
            if entry is None:
                summary['failed'] += 1
                logs.append(SmsMessage(
                    recipient=number,
                    recipient_name=cleaned[number],
                    body=body,
                    sender_name=config['sender_name'],
                    category=category,
                    status=SmsMessage.Status.FAILED,
                    error='Semaphore did not return a delivery record for this number.',
                    match=match,
                    round=round,
                    created_by=created_by,
                ))
                continue

            provider_status = str(entry.get('status') or '').strip()
            failed = provider_status.lower() == 'failed'
            if failed:
                summary['failed'] += 1
            else:
                summary['sent'] += 1
            logs.append(SmsMessage(
                recipient=number,
                recipient_name=cleaned[number],
                body=body,
                sender_name=str(entry.get('sender_name') or config['sender_name'])[:40],
                category=category,
                status=SmsMessage.Status.FAILED if failed else SmsMessage.Status.SENT,
                semaphore_message_id=entry.get('message_id'),
                provider_status=provider_status[:30],
                error='Rejected by the network.' if failed else '',
                match=match,
                round=round,
                created_by=created_by,
            ))
        SmsMessage.objects.bulk_create(logs)

    if summary['failed'] and not summary['error']:
        summary['error'] = 'Some messages were rejected by Semaphore.'
    return summary


def send_sms(number, body, *, category=SmsMessage.Category.MANUAL,
             recipient_name='', match=None, created_by=None):
    return send_bulk_sms(
        [(number, recipient_name)],
        body,
        category=category,
        match=match,
        created_by=created_by,
    )


def _plural(count, noun, plural=None):
    """``'1 match'`` / ``'3 matches'`` for the bulk summary banners."""
    if count == 1:
        return f'1 {noun}'
    return f'{count} {plural or noun + "s"}'


def describe_summary(summary):
    """Short human-readable result for the messages framework."""
    if summary.get('error'):
        text = summary['error']
        if summary.get('sent'):
            text = f"{summary['sent']} message(s) sent. {text}"
    elif summary.get('sent'):
        text = f"SMS sent to {summary['sent']} recipient(s)."
        if summary.get('failed'):
            text += f" {summary['failed']} failed."
        if summary.get('skipped'):
            text += f" {summary['skipped']} skipped."
    else:
        text = summary.get('detail') or 'No SMS was sent.'
    if summary.get('covered'):
        text = f"{summary['covered']} covered. {text}"
    return text


def get_account_balance(force=False):
    """Return ``(account_dict, error)``; cached for five minutes."""
    if not is_configured():
        return None, 'SMS is disabled or SEMAPHORE_API_KEY is missing.'
    if not force:
        cached = cache.get(BALANCE_CACHE_KEY)
        if cached is not None:
            return cached.get('account'), cached.get('error')

    config = get_config()
    url = f"{settings.SEMAPHORE_ACCOUNT_URL}?{parse.urlencode({'apikey': config['api_key']})}"
    account, error_message = None, ''
    try:
        with request.urlopen(url, timeout=int(settings.SEMAPHORE_TIMEOUT)) as response:
            account = json.loads(response.read().decode('utf-8', errors='replace'))
    except error.HTTPError as exc:
        error_message = f'Semaphore returned HTTP {exc.code} while checking the balance.'
    except Exception as exc:  # pragma: no cover - network edge cases
        error_message = f'Could not check the Semaphore balance: {exc}'

    cache.set(
        BALANCE_CACHE_KEY,
        {'account': account, 'error': error_message},
        BALANCE_CACHE_SECONDS,
    )
    return account, error_message


# ---------------------------------------------------------------------------
# Recipients
# ---------------------------------------------------------------------------

def _sms_allowed(user):
    """Team staff/participants can opt out from Settings; default is on."""
    try:
        preference = user.notification_preferences
    except Exception:
        return True
    return preference.sms_enabled


def _profile_phone(user):
    try:
        return (user.account_profile.phone or '').strip()
    except Exception:
        return ''


def _add_recipient(collected, phone, name):
    normalized = normalize_phone_number(phone)
    if not normalized:
        return
    if normalized not in collected or (not collected[normalized] and name):
        collected[normalized] = (name or '').strip()


def _participant_recipient(collected, participant):
    if participant is None:
        return
    if participant.user_id:
        user = participant.user
        if not user.is_active or not _sms_allowed(user):
            return
        phone = _profile_phone(user) or participant.phone
    else:
        phone = participant.phone
    _add_recipient(collected, phone, participant.name)


def _add_team_recipients(collected, team, include_team_players):
    """Add the team's staff (and optionally its active players) to ``collected``."""
    for assignment in team.staff_assignments.all():
        user = assignment.user
        if not user.is_active or not _sms_allowed(user):
            continue
        name = user.get_full_name().strip() or user.username
        _add_recipient(collected, _profile_phone(user), f'{name} ({team.name})')
    if include_team_players:
        for membership in team.memberships.all():
            if membership.status != 'ACTIVE':
                continue
            _participant_recipient(collected, membership.participant)


def recipients_for_match(match, include_team_players=None):
    """Return ``[(phone, name), ...]`` for everyone competing in ``match``.

    Team events notify the team manager/coach (and optionally every active
    player when ``SEMAPHORE_NOTIFY_TEAM_PLAYERS`` is on). Individual events
    notify the participant. Duplicate numbers are collapsed.
    """
    if include_team_players is None:
        include_team_players = bool(getattr(settings, 'SEMAPHORE_NOTIFY_TEAM_PLAYERS', False))

    collected = {}
    entries = (
        match.entries
        .select_related('team', 'participant', 'participant__user')
        .prefetch_related(
            'team__staff_assignments__user__account_profile',
            'team__staff_assignments__user__notification_preferences',
            'team__memberships__participant__user',
        )
        .order_by('side')
    )
    for entry in entries:
        if entry.team_id:
            _add_team_recipients(collected, entry.team, include_team_players)
        else:
            _participant_recipient(collected, entry.participant)
    return [(phone, name) for phone, name in collected.items()]


def recipients_for_competition(competition, include_team_players=None):
    """Return ``[(phone, name), ...]`` for a socio-cultural competition.

    Cultural events have no matches, so the audience is every participant
    registered to the competition plus the staff of the delegations entered
    through the review queue. Rejected entries and opted-out accounts are
    skipped and duplicate numbers are collapsed.
    """
    if include_team_players is None:
        include_team_players = bool(getattr(settings, 'SEMAPHORE_NOTIFY_TEAM_PLAYERS', False))

    collected = {}
    participants = (
        competition.participants
        .select_related('user')
        .order_by('name')
    )
    for participant in participants:
        _participant_recipient(collected, participant)

    registrations = (
        competition.registrations
        .exclude(status=EventRegistration.Status.REJECTED)
        .filter(team__isnull=False)
        .select_related('team')
        .prefetch_related(
            'team__staff_assignments__user__account_profile',
            'team__staff_assignments__user__notification_preferences',
            'team__memberships__participant__user',
        )
    )
    for registration in registrations:
        _add_team_recipients(collected, registration.team, include_team_players)

    return sorted(collected.items())


# ---------------------------------------------------------------------------
# Message templates
# ---------------------------------------------------------------------------

def _local_time(value):
    if value is None:
        return None
    if timezone.is_naive(value):
        value = timezone.make_aware(value, timezone.get_current_timezone())
    zone = ZoneInfo(get_config()['timezone'])
    return timezone.localtime(value, zone)


def format_match_time(match):
    value = match.scheduled_start
    if value is None:
        return 'a time to be announced'
    return _local_time(value).strftime('%b %d, %Y %I:%M %p').replace(' 0', ' ')


def format_match_venue(match):
    return match.venue.name if match.venue_id else 'venue to be announced'


def build_schedule_message(match, change='scheduled'):
    prefix = 'RESCHEDULED' if change == 'rescheduled' else 'SCHEDULE'
    return (
        f'[Competrack] {prefix}: {match.contestants_display()} - {match.event.name} '
        f'({match.label}) on {format_match_time(match)} at {format_match_venue(match)}. '
        'Please arrive 15 mins early.'
    )


def build_reminder_message(match):
    return (
        f'[Competrack] REMINDER: {match.contestants_display()} - {match.event.name} '
        f'({match.label}) starts {format_match_time(match)} at {format_match_venue(match)}. '
        'Please be early.'
    )


def build_start_message(match):
    return (
        f'[Competrack] STARTING NOW: {match.contestants_display()} - {match.event.name} '
        f'({match.label}) at {format_match_venue(match)}.'
    )


def build_live_message(match):
    return (
        f'[Competrack] LIVE: {match.contestants_display()} - {match.event.name} '
        f'({match.label}) is ongoing at {format_match_venue(match)}.'
    )


def _score_text(entry):
    if entry.score is None:
        return '-'
    try:
        value = entry.score
        if value == value.to_integral_value():
            return str(int(value))
        return format(value.normalize(), 'f')
    except (AttributeError, TypeError, ValueError):
        return str(entry.score)


def build_result_message(match):
    entries = list(match.entries.all())
    scoreline = ' vs '.join(
        f'{entry.display_name} {_score_text(entry)}' for entry in entries
    ) or match.contestants_display()
    winner = match.winner
    if winner is not None:
        outcome = f'Winner: {winner.display_name}.'
    elif any(entry.is_draw for entry in entries):
        outcome = 'Result: draw.'
    else:
        outcome = ''
    return (
        f'[Competrack] RESULT: {scoreline} - {match.event.name} ({match.label}). {outcome}'
    ).strip()


def build_status_message(match, status):
    return (
        f'[Competrack] {status.upper()}: {match.contestants_display()} - {match.event.name} '
        f'({match.label}) at {format_match_venue(match)}. Watch for the new schedule.'
    )


def format_competition_window(competition):
    """When a socio-cultural competition runs, for texts that have no match clock."""
    start = _local_time(competition.start_date)
    end = _local_time(competition.end_date)
    if start is None:
        return 'a time to be announced'
    if end is None or start.date() == end.date():
        return start.strftime('%b %d, %Y %I:%M %p').replace(' 0', ' ')
    return (
        f'{start.strftime("%b %d, %Y").replace(" 0", " ")} to '
        f'{end.strftime("%b %d, %Y").replace(" 0", " ")}'
    )


def _session_name(round_obj):
    return f'{round_obj.name} of {round_obj.competition.name}'


def build_cultural_schedule_message(round_obj, change='scheduled'):
    prefix = 'RESCHEDULED' if change == 'rescheduled' else 'SCHEDULE'
    return (
        f'[Competrack] {prefix}: {_session_name(round_obj)} runs '
        f'{format_competition_window(round_obj.competition)}. '
        'Please confirm your slot with your delegation head.'
    )


def build_cultural_reminder_message(round_obj):
    return (
        f'[Competrack] REMINDER: {_session_name(round_obj)} starts '
        f'{format_competition_window(round_obj.competition)}. Please be early.'
    )


def build_cultural_start_message(round_obj):
    return (
        f'[Competrack] STARTING NOW: {_session_name(round_obj)}. '
        'Contestants please report to the stage area.'
    )


def build_cultural_live_message(round_obj):
    return f'[Competrack] LIVE: {_session_name(round_obj)} is ongoing.'


def build_cultural_result_message(round_obj):
    return (
        f'[Competrack] RESULT: {_session_name(round_obj)} is finished. '
        'Scores are posted on the scoreboard.'
    )


def build_cultural_status_message(round_obj, status):
    return (
        f'[Competrack] {status.upper()}: {_session_name(round_obj)}. '
        'Watch for the new schedule.'
    )


_NOTIFY_KINDS = {
    'scheduled': (SmsMessage.Category.SCHEDULE, build_schedule_message),
    'rescheduled': (SmsMessage.Category.RESCHEDULE, lambda match: build_schedule_message(match, 'rescheduled')),
    'reminder': (SmsMessage.Category.REMINDER, build_reminder_message),
    'start': (SmsMessage.Category.MATCH_START, build_start_message),
    'live': (SmsMessage.Category.MATCH_START, build_live_message),
    'result': (SmsMessage.Category.RESULT, build_result_message),
    'postponed': (SmsMessage.Category.RESCHEDULE, lambda match: build_status_message(match, 'postponed')),
    'cancelled': (SmsMessage.Category.RESCHEDULE, lambda match: build_status_message(match, 'cancelled')),
}

# Kinds offered in the UI: (value, button label, who receives what). Every value
# must exist in ``_NOTIFY_KINDS`` above, otherwise the picker silently fails.
NOTIFY_KIND_CHOICES = (
    ('scheduled', 'Schedule', 'Match details so teams know when and where to report.'),
    ('rescheduled', 'Reschedule', 'New time or venue for an already announced match.'),
    ('reminder', 'Reminder', 'Heads-up shortly before the match starts.'),
    ('start', 'Start', 'The match is starting now.'),
    ('live', 'Live', 'The match is ongoing.'),
    ('result', 'Result', 'Final score and winner.'),
    ('postponed', 'Postpone', 'The match is postponed pending a new schedule.'),
    ('cancelled', 'Cancel', 'The match is cancelled.'),
)

NOTIFY_KIND_LABELS = {value: label for value, label, _ in NOTIFY_KIND_CHOICES}

# Socio-cultural rounds reuse the same kind values so one picker and one
# validation list serve both, but the wording talks about rounds and contestants.
_CULTURAL_KINDS = {
    'scheduled': (SmsMessage.Category.SCHEDULE, build_cultural_schedule_message),
    'rescheduled': (
        SmsMessage.Category.RESCHEDULE,
        lambda round_obj: build_cultural_schedule_message(round_obj, 'rescheduled'),
    ),
    'reminder': (SmsMessage.Category.REMINDER, build_cultural_reminder_message),
    'start': (SmsMessage.Category.MATCH_START, build_cultural_start_message),
    'live': (SmsMessage.Category.MATCH_START, build_cultural_live_message),
    'result': (SmsMessage.Category.RESULT, build_cultural_result_message),
    'postponed': (
        SmsMessage.Category.RESCHEDULE,
        lambda round_obj: build_cultural_status_message(round_obj, 'postponed'),
    ),
    'cancelled': (
        SmsMessage.Category.RESCHEDULE,
        lambda round_obj: build_cultural_status_message(round_obj, 'cancelled'),
    ),
}

CULTURAL_KIND_CHOICES = (
    ('scheduled', 'Schedule', 'Round details so contestants know when to report.'),
    ('rescheduled', 'Reschedule', 'New time for an already announced round.'),
    ('reminder', 'Reminder', 'Heads-up shortly before the round starts.'),
    ('start', 'Start', 'The round is starting now.'),
    ('live', 'Live', 'The round is ongoing.'),
    ('result', 'Result', 'The round is over and the scores are posted.'),
    ('postponed', 'Postpone', 'The round is postponed pending a new schedule.'),
    ('cancelled', 'Cancel', 'The round is cancelled.'),
)


def notify_match(match, kind, *, created_by=None, include_team_players=None):
    """Build and send the SMS for a match event.

    ``kind`` is one of ``scheduled``, ``rescheduled``, ``reminder``, ``start``,
    ``live``, ``result``, ``postponed`` or ``cancelled``. Never raises: a match
    save or result must succeed even when the SMS gateway is down.
    """
    try:
        return _notify_match(
            match,
            kind,
            created_by=created_by,
            include_team_players=include_team_players,
        )
    except Exception as exc:  # pragma: no cover - defensive safety net
        summary = _empty_summary()
        summary['error'] = f'SMS could not be sent: {exc}'
        return summary


def _notify_match(match, kind, *, created_by=None, include_team_players=None):
    if kind not in _NOTIFY_KINDS:
        summary = _empty_summary()
        summary['error'] = f'Unknown SMS type: {kind}'
        return summary

    category, builder = _NOTIFY_KINDS[kind]
    summary = _empty_summary()
    recipients = recipients_for_match(match, include_team_players=include_team_players)
    if not recipients:
        summary['detail'] = (
            'No mobile numbers are on file for this match. Add a phone number to '
            'the team manager/coach account or participant profile.'
        )
        return summary

    return send_bulk_sms(
        recipients,
        builder(match),
        category=category,
        match=match,
        created_by=created_by,
    )


def notify_round(round_obj, kind, *, created_by=None):
    """Build and send the SMS for one socio-cultural round.

    Cultural events have no matches, so every registered contestant of the
    competition receives the same text about this round. Never raises.
    """
    try:
        return _notify_round(round_obj, kind, created_by=created_by)
    except Exception as exc:  # pragma: no cover - defensive safety net
        summary = _empty_summary()
        summary['error'] = f'SMS could not be sent: {exc}'
        return summary


def _notify_round(round_obj, kind, *, created_by=None):
    if kind not in _CULTURAL_KINDS:
        summary = _empty_summary()
        summary['error'] = f'Unknown SMS type: {kind}'
        return summary

    category, builder = _CULTURAL_KINDS[kind]
    summary = _empty_summary()
    recipients = recipients_for_competition(round_obj.competition)
    if not recipients:
        summary['detail'] = (
            'No mobile numbers are on file for this competition. Register the '
            'contestants with a phone number before sending.'
        )
        return summary

    return send_bulk_sms(
        recipients,
        builder(round_obj),
        category=category,
        round=round_obj,
        created_by=created_by,
    )


def notify_matches(matches, kind, *, created_by=None, include_team_players=None):
    """Send one update type across a whole schedule (bulk notify).

    Every match needs its own text because the time, venue and contestants
    differ, so this walks the matches with :func:`notify_match` and merges the
    individual reports into one summary. Never raises.
    """
    def send(match, session_kind):
        return notify_match(
            match,
            session_kind,
            created_by=created_by,
            include_team_players=include_team_players,
        )

    return _notify_sessions(matches, kind, send, 'match', 'matches')


def notify_rounds(rounds, kind, *, created_by=None):
    """Send one update type across every round of a socio-cultural competition."""
    def send(round_obj, session_kind):
        return notify_round(round_obj, session_kind, created_by=created_by)

    return _notify_sessions(rounds, kind, send, 'round', 'rounds')


def _notify_sessions(targets, kind, send, noun, plural):
    """Merge per-session reports into one bulk summary, used by both notifiers."""
    summary = _empty_summary()
    summary['without_numbers'] = 0
    problems = []
    covered = 0

    for target in targets:
        item = send(target, kind)
        covered += 1
        for key in ('recipients', 'sent', 'failed', 'skipped'):
            summary[key] += int(item.get(key) or 0)
        if item.get('error') and len(problems) < 3:
            problems.append(str(item['error']))
        if not item.get('sent') and not item.get('skipped') and item.get('detail'):
            summary['without_numbers'] += 1

    summary['covered'] = _plural(covered, noun, plural)
    if problems and not summary['error']:
        summary['error'] = '; '.join(problems)
    if summary['without_numbers'] and not summary['sent']:
        summary['detail'] = (
            f"None of the {summary['without_numbers']} {plural} have a mobile "
            'number on file. Add the number to the team manager/coach account or '
            'the participant profile first.'
        )
    return summary
