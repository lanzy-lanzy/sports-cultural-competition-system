from django.conf import settings
from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from accounts.access import management_required
from sports.models import Match

from .models import SmsMessage
from .services import (
    describe_summary,
    get_account_balance,
    get_config,
    is_configured,
    masked_api_key,
    notify_match,
    send_sms,
)


@management_required
def sms_dashboard(request):
    if request.method == 'POST':
        action = request.POST.get('action', 'test')
        if action == 'refresh_balance':
            get_account_balance(force=True)
            return redirect('sms_dashboard')

        number = request.POST.get('number', '').strip()
        body = request.POST.get('message', '').strip()
        if not number or not body:
            messages.error(request, 'Enter both a mobile number and a message.')
            return redirect('sms_dashboard')
        summary = send_sms(
            number,
            body,
            category=SmsMessage.Category.TEST,
            created_by=request.user,
        )
        level = messages.SUCCESS if summary['sent'] else messages.WARNING
        messages.add_message(request, level, describe_summary(summary))
        return redirect('sms_dashboard')

    queryset = SmsMessage.objects.select_related('match__event', 'created_by')
    category = request.GET.get('category', '')
    status = request.GET.get('status', '')
    if category in SmsMessage.Category.values:
        queryset = queryset.filter(category=category)
    if status in SmsMessage.Status.values:
        queryset = queryset.filter(status=status)

    today = timezone.localdate()
    stats = {
        'total': SmsMessage.objects.count(),
        'today': SmsMessage.objects.filter(created_at__date=today).count(),
        'sent': SmsMessage.objects.filter(status=SmsMessage.Status.SENT).count(),
        'failed': SmsMessage.objects.filter(status=SmsMessage.Status.FAILED).count(),
    }

    balance = None
    balance_error = ''
    if request.GET.get('balance') == '1':
        balance, balance_error = get_account_balance(force=True)

    config = get_config()
    return render(request, 'sms/dashboard.html', {
        'messages_list': queryset[:100],
        'categories': SmsMessage.Category.choices,
        'statuses': SmsMessage.Status.choices,
        'filter_category': category,
        'filter_status': status,
        'stats': stats,
        'configured': is_configured(),
        'enabled': config['enabled'],
        'dry_run': config['dry_run'],
        'sender_name': config['sender_name'],
        'masked_key': masked_api_key(),
        'balance': balance,
        'balance_error': balance_error,
        'timezone_name': config['timezone'],
        'notify_team_players': getattr(settings, 'SEMAPHORE_NOTIFY_TEAM_PLAYERS', False),
    })


@management_required
@require_POST
def sms_notify_match(request, match_id):
    match = get_object_or_404(
        Match.objects.select_related('event', 'event__competition', 'venue'),
        id=match_id,
    )
    allowed = {'scheduled', 'rescheduled', 'reminder', 'start', 'live', 'result',
               'postponed', 'cancelled'}
    kind = request.POST.get('kind', '').strip()
    if kind not in allowed:
        messages.error(request, 'Choose a valid SMS update type.')
        return redirect('match_schedule', event_id=match.event_id)

    summary = notify_match(match, kind, created_by=request.user)
    level = messages.SUCCESS if summary['sent'] else messages.WARNING
    messages.add_message(request, level, describe_summary(summary))
    return redirect('match_schedule', event_id=match.event_id)
