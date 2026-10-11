from django.contrib.auth.models import User
from django.core.mail import send_mail
from django.db import transaction
from django.conf import settings
from django.utils import timezone

from accounts.access import MANAGEMENT_ROLES
from accounts.models import UserProfile

from .models import Announcement, Notification, NotificationPreference


def recipients_for_audience(audience):
    users = User.objects.filter(is_active=True)
    if audience == Announcement.Audience.MANAGEMENT:
        return users.filter(account_profile__role__in=MANAGEMENT_ROLES)
    if audience == Announcement.Audience.JUDGES:
        return users.filter(account_profile__role=UserProfile.Role.JUDGE)
    if audience == Announcement.Audience.PARTICIPANTS:
        return users.filter(account_profile__role=UserProfile.Role.PARTICIPANT)
    if audience == Announcement.Audience.TEAM_MANAGERS:
        return users.filter(account_profile__role=UserProfile.Role.TEAM_MANAGER)
    return users


def notify_users(users, title, body='', link='', send_email=True):
    """Create in-app notifications for ``users`` and optionally email them."""
    recipients = [user for user in users if user.is_active]
    if not recipients:
        return 0

    Notification.objects.bulk_create([
        Notification(recipient=user, title=title, body=body, link=link)
        for user in recipients
    ])

    if send_email:
        email_recipients = []
        for user in recipients:
            pref, _ = NotificationPreference.objects.get_or_create(user=user)
            if pref.email_enabled and user.email:
                email_recipients.append(user.email)
        if email_recipients:
            send_mail(
                subject=title,
                message=f'{body}\n\n{link}' if link else body,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=email_recipients,
                fail_silently=True,
            )

    return len(recipients)


@transaction.atomic
def publish_announcement(announcement):
    """Publish an announcement, notify the audience, and record the publish time."""
    announcement.is_published = True
    announcement.published_at = timezone.now()
    announcement.save()

    recipients = recipients_for_audience(announcement.audience)
    link = ''
    if announcement.competition_id:
        from django.urls import reverse
        link = reverse('competition_detail', args=[announcement.competition_id])

    notify_users(
        recipients,
        title=announcement.title,
        body=announcement.body,
        link=link,
    )
    return announcement
