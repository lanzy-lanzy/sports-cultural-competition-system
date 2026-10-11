from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from competitions.models import Competition
from sports.models import SportType, SportsEvent
from teams.models import Team
from accounts.models import UserProfile

from .models import Protest


class ProtestTest(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser('admin', 'a@a.com', 'pass')
        self.competition = Competition.objects.create(
            name='Chess Open',
            description='Annual chess competition',
            start_date='2026-01-10',
            end_date='2026-01-12',
            status='ACTIVE',
            created_by=self.admin,
        )
        self.manager = User.objects.create_user('manager', 'm@example.com', 'pass')
        self.manager.account_profile.role = UserProfile.Role.TEAM_MANAGER
        self.manager.account_profile.save(update_fields=['role', 'updated_at'])

    def _create_protest(self):
        return Protest.objects.create(
            submitter=self.manager,
            competition=self.competition,
            title='Unfair ruling',
            description='The decision on our match was wrong.',
        )

    def test_team_manager_submits_protest(self):
        self.client.force_login(self.manager)
        resp = self.client.post(reverse('submit_protest'), {
            'target_type': 'competition',
            'competition': self.competition.id,
            'title': 'Protest the ruling',
            'description': 'The scoring table made an error.',
        })
        self.assertRedirects(resp, reverse('my_protests'))
        protest = Protest.objects.get(title='Protest the ruling')
        self.assertEqual(protest.submitter, self.manager)
        self.assertEqual(protest.status, Protest.Status.SUBMITTED)

    def test_submitter_tracks_status(self):
        protest = self._create_protest()
        self.client.force_login(self.manager)
        resp = self.client.get(reverse('my_protests'))
        self.assertContains(resp, 'Unfair ruling')
        self.assertContains(resp, 'Submitted')

    def test_management_reviews_and_resolves(self):
        protest = self._create_protest()
        self.client.force_login(self.admin)
        resp = self.client.post(reverse('protest_review', args=[protest.id]), {
            'status': 'RESOLVED',
            'decision': 'The appeal is upheld.',
            'reviewers': [self.admin.id],
        })
        self.assertRedirects(resp, reverse('protest_detail', args=[protest.id]))
        protest.refresh_from_db()
        self.assertEqual(protest.status, Protest.Status.RESOLVED)
        self.assertEqual(protest.decision, 'The appeal is upheld.')
        self.assertEqual(protest.reviewed_by, self.admin)
        self.assertTrue(protest.reviewers.filter(id=self.admin.id).exists())
        from audit.models import AuditLog
        self.assertTrue(AuditLog.objects.filter(action='PROTEST_REVIEW').exists())

    def test_spectator_cannot_open_review_queue(self):
        viewer = User.objects.create_user('viewer', 'v@example.com', 'pass')
        self.client.force_login(viewer)
        self.assertEqual(self.client.get(reverse('protest_list')).status_code, 403)