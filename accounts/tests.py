from django.contrib.auth.models import User
from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse

from competitions.models import Competition
from judges.models import Judge, JudgeAssignment
from .models import UserProfile


class AccountTest(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser('admin', 'a@a.com', 'pass')

    def test_register_creates_judge_and_redirects(self):
        resp = self.client.post(reverse('register'), {
            'username': 'newjudge', 'email': 'n@a.com',
            'password1': 'A-Strong-Competition-Pass-928!',
            'password2': 'A-Strong-Competition-Pass-928!',
            'full_name': 'Jane Doe', 'phone': '123', 'role': 'JUDGE',
        })
        self.assertRedirects(resp, reverse('login'))
        self.assertTrue(Judge.objects.filter(user__username='newjudge').exists())
        self.assertEqual(
            UserProfile.objects.get(user__username='newjudge').role,
            UserProfile.Role.JUDGE,
        )

    def test_public_registration_rejects_management_roles(self):
        resp = self.client.post(reverse('register'), {
            'username': 'organizer', 'email': 'organizer@example.com',
            'password1': 'A-Strong-Competition-Pass-928!',
            'password2': 'A-Strong-Competition-Pass-928!',
            'full_name': 'Event Organizer', 'phone': '123',
            'role': UserProfile.Role.EVENT_ORGANIZER,
        })

        self.assertEqual(resp.status_code, 200)
        self.assertFalse(User.objects.filter(username='organizer').exists())
        self.assertContains(resp, 'Select a valid choice')

    def test_landing_page_has_institutional_branding_and_primary_actions(self):
        resp = self.client.get(reverse('landing_page'))

        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'images/jhcsc_logo.png')
        self.assertContains(resp, 'images/it_logo.png')
        self.assertContains(resp, reverse('login'))
        self.assertContains(resp, reverse('register'))
        self.assertContains(resp, 'Every score counts.')

    def test_auth_pages_share_institutional_branding(self):
        for route_name in ('login', 'register'):
            with self.subTest(route_name=route_name):
                resp = self.client.get(reverse(route_name))
                self.assertContains(resp, 'images/jhcsc_logo.png')
                self.assertContains(resp, 'images/it_logo.png')
                self.assertContains(resp, reverse('landing_page'))

    def test_invalid_login_shows_a_clear_error(self):
        resp = self.client.post(reverse('login'), {
            'username': 'missing-user',
            'password': 'incorrect-password',
        })

        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Invalid username or password. Please try again.')

    def test_dashboard_requires_login(self):
        resp = self.client.get(reverse('dashboard'))
        self.assertEqual(resp.status_code, 302)

    def test_login_redirects_admin_to_dashboard(self):
        resp = self.client.post(reverse('login'), {'username': 'admin', 'password': 'pass'})
        self.assertRedirects(resp, reverse('dashboard'))

    def test_edit_profile_updates_account_details(self):
        self.client.login(username='admin', password='pass')
        resp = self.client.post(reverse('edit_profile'), {
            'full_name': 'System Administrator', 'username': 'admin',
            'email': 'new@a.com', 'phone': '09170000000',
        })
        self.assertRedirects(resp, reverse('edit_profile'))
        self.admin.refresh_from_db()
        self.assertEqual(self.admin.get_full_name(), 'System Administrator')
        self.assertEqual(self.admin.account_profile.phone, '09170000000')

    def test_login_redirects_spectator_to_portal(self):
        User.objects.create_user('viewer', 'viewer@example.com', 'pass')
        resp = self.client.post(reverse('login'), {'username': 'viewer', 'password': 'pass'})
        self.assertRedirects(resp, reverse('portal_home'))

    def test_spectator_cannot_open_management_routes(self):
        viewer = User.objects.create_user('viewer', 'viewer@example.com', 'pass')
        self.client.force_login(viewer)
        self.assertEqual(self.client.get(reverse('dashboard')).status_code, 403)
        self.assertEqual(self.client.get(reverse('create_competition')).status_code, 403)
        self.assertEqual(self.client.get(reverse('participant_management')).status_code, 403)

    def test_administrator_can_change_user_role_and_status(self):
        target = User.objects.create_user('coordinator', 'c@example.com', 'pass')
        self.client.force_login(self.admin)
        resp = self.client.post(reverse('update_user_access', args=[target.id]), {
            'role': UserProfile.Role.SPORTS_COORDINATOR,
            'is_active': 'on',
        })

        self.assertRedirects(resp, reverse('user_management') + '?page=1')
        target.refresh_from_db()
        self.assertEqual(target.account_profile.role, UserProfile.Role.SPORTS_COORDINATOR)
        self.assertTrue(target.is_staff)

    @override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
    def test_password_reset_sends_recovery_link(self):
        User.objects.create_user('recover', 'recover@example.com', 'pass')
        resp = self.client.post(reverse('password_reset'), {'email': 'recover@example.com'})

        self.assertRedirects(resp, reverse('password_reset_done'))
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('/password-reset/', mail.outbox[0].body)
