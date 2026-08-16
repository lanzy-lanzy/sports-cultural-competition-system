from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from competitions.models import Competition, Round
from .models import Judge, JudgeAssignment


class JudgeTest(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser('admin', 'a@a.com', 'pass')
        self.client.login(username='admin', password='pass')
        self.competition = Competition.objects.create(
            name='Comp', description='d', status='ACTIVE',
            start_date='2026-01-01 00:00:00', end_date='2026-01-02 00:00:00',
            created_by=self.admin,
        )
        self.round = Round.objects.create(
            competition=self.competition, name='R', description='d', order=1,
            status='PENDING', weight_percentage=100,
        )
        self.judge_user = User.objects.create_user('judge', 'j@a.com', 'pass')
        self.judge = Judge.objects.create(user=self.judge_user, phone='1', status='ACTIVE')

    def test_assign_judges_to_rounds(self):
        resp = self.client.post(reverse('assign_judges', args=[self.competition.id]), {
            'judges': [self.judge.id], 'rounds': [self.round.id],
        })
        self.assertRedirects(resp, reverse('manage_judges', args=[self.competition.id]))
        assignment = JudgeAssignment.objects.get(judge=self.judge, competition=self.competition)
        self.assertEqual(list(assignment.rounds.all()), [self.round])
        self.assertEqual(assignment.status, 'ACTIVE')

    def test_judge_dashboard_only_for_judges(self):
        self.client.logout()
        self.client.login(username='judge', password='pass')
        resp = self.client.get(reverse('judge_dashboard'))
        self.assertEqual(resp.status_code, 200)

    def test_judge_history_only_for_judges(self):
        resp = self.client.get(reverse('judge_history'))
        self.assertRedirects(resp, reverse('dashboard'))

    def test_judge_history_scoped_to_own_scores(self):
        self.client.logout()
        other_user = User.objects.create_user('other', 'o@a.com', 'pass')
        Judge.objects.create(user=other_user, phone='2', status='ACTIVE')

        self.client.login(username='judge', password='pass')
        resp = self.client.get(reverse('judge_history'))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'No Scoring History Yet')
