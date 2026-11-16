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
        self.assertEqual(resp.status_code, 403)

    def test_judge_history_scoped_to_own_scores(self):
        self.client.logout()
        other_user = User.objects.create_user('other', 'o@a.com', 'pass')
        Judge.objects.create(user=other_user, phone='2', status='ACTIVE')

        self.client.login(username='judge', password='pass')
        resp = self.client.get(reverse('judge_history'))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'No Scoring History Yet')


class SportsJudgingSeparationTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_superuser('separation-admin', 'a@example.com', None)
        base = dict(description='Test', created_by=cls.admin, status='ACTIVE',
                    start_date='2026-01-01T00:00:00Z', end_date='2026-02-01T00:00:00Z')
        cls.sports = Competition.objects.create(name='Sports excluded', kind='SPORTS', **base)
        cls.cultural = Competition.objects.create(name='Cultural included', kind='CULTURAL', **base)
        cls.mixed = Competition.objects.create(name='Legacy judged', kind='MIXED', **base)
        cls.round = Round.objects.create(competition=cls.sports, name='Legacy sports round', order=1)
        cls.user = User.objects.create_user('legacy-judge')
        cls.user.account_profile.role = 'JUDGE'
        cls.user.account_profile.save()
        cls.judge = Judge.objects.create(user=cls.user, phone='1')
        cls.assignment = JudgeAssignment.objects.create(judge=cls.judge, competition=cls.sports)
        cls.assignment.rounds.add(cls.round)

    def setUp(self):
        self.client.force_login(self.admin)

    def test_management_lists_only_judged_competitions(self):
        response = self.client.get(reverse('judge_management'))
        self.assertContains(response, 'Cultural included')
        self.assertContains(response, 'Legacy judged')
        self.assertNotContains(response, 'Sports excluded')

    def test_sports_assignment_routes_reject_get_and_post_without_mutations(self):
        routes = [('manage_judges', [self.sports.pk]), ('assign_judges', [self.sports.pk]),
                  ('edit_judge_assignment', [self.sports.pk, self.assignment.pk]),
                  ('delete_judge_assignment', [self.sports.pk, self.assignment.pk])]
        for name, args in routes:
            for method in [self.client.get, self.client.post]:
                with self.subTest(name=name, method=method.__name__):
                    response = method(reverse(name, args=args), {'judges': [self.judge.pk], 'rounds': [self.round.pk]})
                    self.assertEqual(response.status_code, 404)
        self.assertEqual(JudgeAssignment.objects.filter(competition=self.sports).count(), 1)

    def test_sports_details_and_reports_have_no_judge_controls(self):
        response = self.client.get(reverse('competition_detail', args=[self.sports.pk]))
        self.assertNotContains(response, reverse('manage_judges', args=[self.sports.pk]))
        response = self.client.get(reverse('reports_home'))
        self.assertNotContains(response, reverse('export_judge_scores_csv', args=[self.sports.pk]))
        self.assertContains(response, reverse('export_judge_scores_csv', args=[self.cultural.pk]))

    def test_sports_judge_exports_are_unavailable(self):
        for name in ['export_judge_scores_csv', 'export_judge_scores_pdf', 'print_judge_scores']:
            self.assertEqual(self.client.get(reverse(name, args=[self.sports.pk])).status_code, 404)

    def test_sports_judged_results_use_medal_tally(self):
        for name in ['competition_results_detail', 'results_print', 'results_reveal', 'generate_pdf_results', 'score_history']:
            self.assertRedirects(self.client.get(reverse(name, args=[self.sports.pk])), reverse('medal_tally', args=[self.sports.pk]))

    def test_legacy_sports_assignments_hidden_from_judge_workspace(self):
        self.client.force_login(self.user)
        for name in ['judge_dashboard', 'judge_profile', 'judge_history']:
            self.assertNotContains(self.client.get(reverse(name)), 'Sports excluded')
        self.assertRedirects(self.client.get(reverse('scoring_panel', args=[self.round.pk])), reverse('judge_dashboard'))
        from scoring.views import _is_assigned_to_round
        self.assertFalse(_is_assigned_to_round(self.judge, self.round))

    def test_cultural_judge_management_stays_available(self):
        self.assertEqual(self.client.get(reverse('manage_judges', args=[self.cultural.pk])).status_code, 200)
