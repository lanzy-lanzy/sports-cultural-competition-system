from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from competitions.models import Competition
from judges.models import Judge, JudgeAssignment


class AccountTest(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser('admin', 'a@a.com', 'pass')

    def test_register_creates_judge_and_redirects(self):
        resp = self.client.post(reverse('register'), {
            'username': 'newjudge', 'email': 'n@a.com',
            'password1': 'secret123', 'full_name': 'Jane Doe', 'phone': '123',
        })
        self.assertRedirects(resp, reverse('login'))
        self.assertTrue(Judge.objects.filter(user__username='newjudge').exists())

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

    def test_edit_profile_redirects_admin_to_dashboard(self):
        self.client.login(username='admin', password='pass')
        resp = self.client.post(reverse('edit_profile'), {
            'username': 'admin', 'email': 'new@a.com',
        })
        self.assertRedirects(resp, reverse('dashboard'))
