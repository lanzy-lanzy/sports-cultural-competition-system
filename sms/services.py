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
                  match=None, created_by=None):
    """Send one message to many recipients through a single Semaphore call.

    ``recipients`` is an iterable of ``(phone, name)`` pairs. Invalid numbers
    are skipped. The returned summary contains counts suitable for a UI
    message, and each recipient gets an :class:`SmsMessage` row.
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


def describe_summary(summary):
    """Short human-readable result for the messages framework."""
    if summary.get('error'):
        text = summary['error']
        if summary.get('sent'):
            text = f"{summary['sent']} message(s) sent. {text}"
        return text
    if summary.get('sent'):
        text = f"SMS sent to {summary['sent']} recipient(s)."
        if summary.get('failed'):
            text += f" {summary['failed']} failed."
        if summary.get('skipped'):
            text += f" {summary['skipped']} skipped."
        return text
    return summary.get('detail') or 'No SMS was sent.'


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
            for assignment in entry.team.staff_assignments.all():
                user = assignment.user
                if not user.is_active or not _sms_allowed(user):
                    continue
                name = user.get_full_name().strip() or user.username
                _add_recipient(collected, _profile_phone(user), f'{name} ({entry.team.name})')
            if include_team_players:
                for membership in entry.team.memberships.all():
                    if membership.status != 'ACTIVE':
                        continue
                    _participant_recipient(collected, membership.participant)
        else:
            _participant_recipient(collected, entry.participant)
    return [(phone, name) for phone, name in collected.items()]


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
