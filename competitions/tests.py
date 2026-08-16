from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from .models import Competition, Round, Criterion
from scoring.models import CompetitionResult


class CompetitionViewTest(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser('admin', 'a@a.com', 'pass')
        self.client.login(username='admin', password='pass')
        self.competition = Competition.objects.create(
            name='Comp', description='d', status='ACTIVE',
            start_date='2026-01-01 00:00:00', end_date='2026-01-02 00:00:00',
            created_by=self.admin,
        )

    def test_create_competition_with_rounds_and_criteria(self):
        data = {
            'name': 'New Comp', 'description': 'desc',
            'start_date': '2026-02-01 00:00:00', 'end_date': '2026-02-02 00:00:00',
            'status': 'DRAFT',
            'round_names[]': ['Round A'], 'round_orders[]': ['1'],
            'round_weights[]': ['100'], 'round_statuses[]': ['PENDING'],
            'criterion_names_1[]': ['C1'], 'criterion_descriptions_1[]': ['x'],
            'criterion_max_scores_1[]': ['50'],
        }
        resp = self.client.post(reverse('create_competition'), data)
        self.assertRedirects(resp, reverse('competition_list'))
        comp = Competition.objects.get(name='NEW COMP')
        self.assertEqual(comp.rounds.count(), 1)
        self.assertEqual(comp.rounds.first().criteria.count(), 1)
        self.assertEqual(comp.rounds.first().criteria.first().max_score, Decimal('50'))

    def test_edit_competition_updates_name(self):
        data = {
            'title': 'Renamed', 'description': 'new',
            'start_date': '2026-03-01 00:00:00', 'end_date': '2026-03-02 00:00:00',
            'status': 'COMPLETED',
        }
        resp = self.client.post(reverse('edit_competition', args=[self.competition.id]), data)
        self.assertRedirects(resp, reverse('competition_detail', args=[self.competition.id]))
        self.competition.refresh_from_db()
        self.assertEqual(self.competition.name, 'RENAMED')
        self.assertEqual(self.competition.status, 'COMPLETED')

    def test_toggle_round_status_flow(self):
        round_obj = Round.objects.create(
            competition=self.competition, name='R', description='d', order=1,
            status='PENDING', weight_percentage=Decimal('100'),
        )
        resp = self.client.post(reverse('toggle_round_status', args=[self.competition.id, round_obj.id]))
        self.assertRedirects(resp, reverse('manage_rounds', args=[self.competition.id]))
        round_obj.refresh_from_db()
        self.assertEqual(round_obj.status, 'ONGOING')

    def test_toggle_round_status_requires_post(self):
        round_obj = Round.objects.create(
            competition=self.competition, name='R', description='d', order=1,
            status='PENDING', weight_percentage=Decimal('100'),
        )
        resp = self.client.get(reverse('toggle_round_status', args=[self.competition.id, round_obj.id]))
        self.assertEqual(resp.status_code, 405)
        round_obj.refresh_from_db()
        self.assertEqual(round_obj.status, 'PENDING')

    def test_cannot_toggle_second_round_to_ongoing(self):
        Round.objects.create(
            competition=self.competition, name='LIVE', description='d', order=1,
            status='ONGOING', weight_percentage=Decimal('50'),
        )
        pending_round = Round.objects.create(
            competition=self.competition, name='NEXT', description='d', order=2,
            status='PENDING', weight_percentage=Decimal('50'),
        )
        self.client.post(reverse('toggle_round_status', args=[self.competition.id, pending_round.id]))
        pending_round.refresh_from_db()
        self.assertEqual(pending_round.status, 'PENDING')

    def test_toggle_completed_round_reopens_it(self):
        round_obj = Round.objects.create(
            competition=self.competition, name='R', description='d', order=1,
            status='COMPLETED', weight_percentage=Decimal('100'),
        )
        self.client.post(reverse('toggle_round_status', args=[self.competition.id, round_obj.id]))
        round_obj.refresh_from_db()
        self.assertEqual(round_obj.status, 'PENDING')

    def test_round_weight_cannot_exceed_100(self):
        Round.objects.create(
            competition=self.competition, name='R', description='d', order=1,
            status='PENDING', weight_percentage=Decimal('80'),
        )
        data = {'name': 'R2', 'description': 'd', 'order': '2', 'weight_percentage': '30'}
        resp = self.client.post(reverse('create_round', args=[self.competition.id]), data)
        self.assertRedirects(resp, reverse('create_round', args=[self.competition.id]))
        self.assertEqual(self.competition.rounds.count(), 1)

    def test_start_and_complete_round(self):
        round_obj = Round.objects.create(
            competition=self.competition, name='R', description='d', order=1,
            status='PENDING', weight_percentage=Decimal('100'),
        )
        self.client.post(reverse('start_round', args=[self.competition.id, round_obj.id]))
        round_obj.refresh_from_db()
        self.assertEqual(round_obj.status, 'ONGOING')

        self.client.post(reverse('complete_round', args=[self.competition.id, round_obj.id]))
        round_obj.refresh_from_db()
        self.assertEqual(round_obj.status, 'COMPLETED')
