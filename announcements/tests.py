from django.contrib.auth.models import User
from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse

from accounts.models import UserProfile
from competitions.models import Competition

from .models import Announcement, Notification


class AnnouncementTest(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser('admin', 'a@a.com', 'pass')
        self.judge_user = User.objects.create_user('judge', 'judge@example.com', 'pass')
        self.judge_user.account_profile.role = UserProfile.Role.JUDGE
        self.judge_user.account_profile.save(update_fields=['role', 'updated_at'])
        self.participant_user = User.objects.create_user('athlete', 'athlete@example.com', 'pass')
        self.participant_user.account_profile.role = UserProfile.Role.PARTICIPANT
        self.participant_user.account_profile.save(update_fields=['role', 'updated_at'])
        self.competition = Competition.objects.create(
            name='Chess Open',
            description='Annual chess competition',
            start_date='2026-01-10',
            end_date='2026-01-12',
            status='ACTIVE',
            created_by=self.admin,
        )

    def _create_announcement(self, audience=Announcement.Audience.ALL, published=False):
        return Announcement.objects.create(
            title='Schedule update',
            body='Round one starts at 8 AM.',
            audience=audience,
            competition=self.competition,
            is_published=published,
            created_by=self.admin,
        )

    @override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
    def test_publish_notifies_audience_and_sends_email(self):
        self.client.force_login(self.admin)
        resp = self.client.post(reverse('create_announcement'), {
            'title': 'New schedule',
            'body': 'Check the latest timings.',
            'competition': self.competition.id,
            'audience': Announcement.Audience.ALL,
            'is_published': 'on',
        })
        self.assertRedirects(resp, reverse('announcement_list'))

        announcement = Announcement.objects.get(title='New schedule')
        self.assertTrue(announcement.is_published)
        self.assertIsNotNone(announcement.published_at)

        self.assertEqual(Notification.objects.filter(recipient=self.judge_user).count(), 1)
        self.assertEqual(Notification.objects.filter(recipient=self.participant_user).count(), 1)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(
            set(mail.outbox[0].recipients()),
            {'a@a.com', 'judge@example.com', 'athlete@example.com'},
        )

    @override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
    def test_audience_targeting_limits_recipients(self):
        announcement = self._create_announcement(audience=Announcement.Audience.JUDGES)
        self.client.force_login(self.admin)
        self.client.post(reverse('toggle_announcement_publish', args=[announcement.id]))

        self.assertTrue(Notification.objects.filter(recipient=self.judge_user).exists())
        self.assertFalse(Notification.objects.filter(recipient=self.participant_user).exists())

    def test_email_notification_preference_suppresses_email(self):
        from .models import NotificationPreference
        NotificationPreference.objects.create(user=self.participant_user, email_enabled=False)
        announcement = self._create_announcement()
        self.client.force_login(self.admin)
        with self.settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend'):
            self.client.post(reverse('toggle_announcement_publish', args=[announcement.id]))
        # Participant still receives the in-app notification, but no email is sent to them.
        self.assertEqual(Notification.objects.filter(recipient=self.participant_user).count(), 1)
        self.assertTrue(all('athlete@example.com' not in message.to for message in mail.outbox))

    def test_user_can_mark_notifications_read(self):
        notification = Notification.objects.create(
            recipient=self.participant_user,
            title='Welcome',
            body='Hello',
        )
        self.client.force_login(self.participant_user)
        self.assertContains(self.client.get(reverse('notification_list')), 'Welcome')
        self.client.post(reverse('mark_notification_read', args=[notification.id]))
        notification.refresh_from_db()
        self.assertTrue(notification.is_read)

    def test_announcements_require_management(self):
        self.client.force_login(self.participant_user)
        self.assertEqual(self.client.get(reverse('announcement_list')).status_code, 403)
        self.assertEqual(self.client.get(reverse('create_announcement')).status_code, 403)
