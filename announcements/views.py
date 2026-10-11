from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from accounts.access import management_required

from .forms import AnnouncementForm
from .models import Announcement, Notification
from .services import publish_announcement


@management_required
def announcement_list(request):
    announcements = Announcement.objects.select_related('created_by', 'competition').order_by('-created_at')
    page_obj = Paginator(announcements, 12).get_page(request.GET.get('page'))
    return render(request, 'announcements/announcement_list.html', {
        'page_obj': page_obj,
        'published_count': Announcement.objects.filter(is_published=True).count(),
    })


@management_required
def create_announcement(request):
    form = AnnouncementForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        announcement = form.save(commit=False)
        announcement.created_by = request.user
        if form.cleaned_data['is_published']:
            publish_announcement(announcement)
            messages.success(request, 'Announcement published and your audience was notified.')
        else:
            announcement.save()
            messages.success(request, 'Announcement saved as a draft.')
        return redirect('announcement_list')
    return render(request, 'announcements/announcement_form.html', {
        'form': form,
        'announcement': None,
        'form_title': 'Create announcement',
    })


@management_required
def edit_announcement(request, announcement_id):
    announcement = get_object_or_404(Announcement, id=announcement_id)
    form = AnnouncementForm(request.POST or None, instance=announcement)
    if request.method == 'POST' and form.is_valid():
        announcement = form.save(commit=False)
        if announcement.is_published and not announcement.published_at:
            publish_announcement(announcement)
        else:
            announcement.save()
        messages.success(request, 'Announcement updated successfully.')
        return redirect('announcement_list')
    return render(request, 'announcements/announcement_form.html', {
        'form': form,
        'announcement': announcement,
        'form_title': 'Edit announcement',
    })


@management_required
@require_POST
def toggle_announcement_publish(request, announcement_id):
    announcement = get_object_or_404(Announcement, id=announcement_id)
    if announcement.is_published:
        announcement.is_published = False
        announcement.save(update_fields=['is_published', 'updated_at'])
        messages.info(request, 'Announcement unpublished.')
    else:
        publish_announcement(announcement)
        from audit.models import record_action_from_request
        record_action_from_request(
            request,
            'ANNOUNCEMENT_PUBLISH',
            target=announcement,
            details=f'Announcement "{announcement.title}" published',
        )
        messages.success(request, 'Announcement published and your audience was notified.')
    return redirect('announcement_list')


@management_required
@require_POST
def delete_announcement(request, announcement_id):
    announcement = get_object_or_404(Announcement, id=announcement_id)
    announcement.delete()
    messages.success(request, 'Announcement deleted.')
    return redirect('announcement_list')


@login_required
def announcement_public(request):
    announcements = Announcement.objects.filter(is_published=True).select_related('created_by', 'competition')
    page_obj = Paginator(announcements.order_by('-published_at'), 12).get_page(request.GET.get('page'))
    return render(request, 'announcements/announcement_public.html', {'page_obj': page_obj})


@login_required
def notification_list(request):
    notifications = request.user.notifications.all()
    page_obj = Paginator(notifications, 20).get_page(request.GET.get('page'))
    unread_ids = list(notifications.filter(is_read=False).values_list('id', flat=True))
    return render(request, 'announcements/notifications.html', {
        'page_obj': page_obj,
        'unread_count': len(unread_ids),
    })


@login_required
@require_POST
def mark_notification_read(request, notification_id):
    notification = get_object_or_404(Notification, id=notification_id, recipient=request.user)
    notification.is_read = True
    notification.save(update_fields=['is_read'])
    return redirect('notification_list')


@login_required
@require_POST
def mark_all_notifications_read(request):
    request.user.notifications.filter(is_read=False).update(is_read=True)
    messages.success(request, 'All notifications marked as read.')
    return redirect('notification_list')
