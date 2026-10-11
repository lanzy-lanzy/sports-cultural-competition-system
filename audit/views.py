from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import render

from accounts.access import management_required

from .models import AuditLog


@management_required
def audit_log_list(request):
    logs = AuditLog.objects.select_related('user', 'content_type')

    action = request.GET.get('action', '')
    query = request.GET.get('q', '').strip()

    if action:
        logs = logs.filter(action=action)
    if query:
        logs = logs.filter(
            Q(user__username__icontains=query)
            | Q(user__email__icontains=query)
            | Q(details__icontains=query)
        )

    page_obj = Paginator(logs, 25).get_page(request.GET.get('page'))

    return render(request, 'audit/audit_log_list.html', {
        'page_obj': page_obj,
        'actions': AuditLog.Action.choices,
        'selected_action': action,
        'query': query,
        'total_count': AuditLog.objects.count(),
    })


@management_required
def clear_audit_logs(request):
    if request.method != 'POST':
        messages.error(request, 'Invalid request.')
        return render(request, 'audit/audit_log_list.html', {
            'page_obj': Paginator(AuditLog.objects.all(), 25).get_page(1),
            'actions': AuditLog.Action.choices,
            'selected_action': '',
            'query': '',
            'total_count': AuditLog.objects.count(),
        })
    AuditLog.objects.all().delete()
    messages.success(request, 'Audit log cleared.')
    return render(request, 'audit/audit_log_list.html', {
        'page_obj': Paginator(AuditLog.objects.all(), 25).get_page(1),
        'actions': AuditLog.Action.choices,
        'selected_action': '',
        'query': '',
        'total_count': AuditLog.objects.count(),
    })