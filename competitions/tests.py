from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from .models import Competition, Round, Criterion
from scoring.models import CompetitionResult
from accounts.models import UserProfile


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
            'status': 'DRAFT', 'kind': 'SPORTS',
            'round_names[]': ['Round A'], 'round_orders[]': ['1'],
            'round_weights[]': ['100'], 'round_statuses[]': ['PENDING'],
            'criterion_names_1[]': ['C1'], 'criterion_descriptions_1[]': ['x'],
            'criterion_max_scores_1[]': ['50'],
        }
        resp = self.client.post(reverse('create_competition'), data)
        self.assertRedirects(resp, reverse('competition_list'))
        comp = Competition.objects.get(name='NEW COMP')
        self.assertEqual(comp.kind, 'SPORTS')
        self.assertEqual(comp.rounds.count(), 1)
        self.assertEqual(comp.rounds.first().criteria.count(), 1)
        self.assertEqual(comp.rounds.first().criteria.first().max_score, Decimal('50'))

    def test_edit_competition_updates_name(self):
        data = {
            'title': 'Renamed', 'description': 'new',
            'start_date': '2026-03-01 00:00:00', 'end_date': '2026-03-02 00:00:00',
            'status': 'COMPLETED', 'kind': 'SPORTS',
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

    def test_create_competition_persists_kind_medals_and_criterion_weights(self):
        data = {
            'name': 'Cultural Fest', 'description': 'desc',
            'start_date': '2026-02-01 00:00:00', 'end_date': '2026-02-02 00:00:00',
            'status': 'DRAFT',
            'kind': 'CULTURAL', 'cultural_event_type': 'DANCE',
            'gold_points': '15', 'silver_points': '8', 'bronze_points': '4',
            'round_names[]': ['Round A'], 'round_orders[]': ['1'],
            'round_weights[]': ['100'], 'round_statuses[]': ['PENDING'],
            'criterion_names_1[]': ['Technique'], 'criterion_descriptions_1[]': ['x'],
            'criterion_max_scores_1[]': ['50'], 'criterion_weights_1[]': ['60'],
        }
        resp = self.client.post(reverse('create_competition'), data)
        self.assertRedirects(resp, reverse('competition_list'))
        comp = Competition.objects.get(name='CULTURAL FEST')
        self.assertEqual(comp.kind, 'CULTURAL')
        self.assertEqual(comp.cultural_event_type, 'DANCE')
        self.assertEqual(comp.gold_points, Decimal('15'))
        self.assertEqual(comp.silver_points, Decimal('8'))
        self.assertEqual(comp.bronze_points, Decimal('4'))
        criterion = comp.rounds.first().criteria.first()
        self.assertEqual(criterion.weight_percentage, Decimal('60'))

    def test_create_competition_rejects_invalid_kind(self):
        data = {
            'name': 'Comp', 'description': 'desc',
            'start_date': '2026-02-01 00:00:00', 'end_date': '2026-02-02 00:00:00',
            'status': 'DRAFT', 'kind': 'NOT_A_KIND',
            'round_names[]': ['Round A'], 'round_orders[]': ['1'],
            'round_weights[]': ['100'], 'round_statuses[]': ['PENDING'],
            'criterion_names_1[]': ['C1'], 'criterion_descriptions_1[]': ['x'],
            'criterion_max_scores_1[]': ['50'],
        }
        resp = self.client.post(reverse('create_competition'), data)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Select the competition category')
        self.assertTrue(resp.context['category_errors'])
        # Nothing is stored when the explicit category selection is invalid.
        self.assertEqual(Competition.objects.filter(name='COMP').count(), 0)

    def test_create_competition_requires_explicit_category(self):
        data = {
            'name': 'No Category', 'description': 'desc',
            'start_date': '2026-02-01 00:00:00', 'end_date': '2026-02-02 00:00:00',
            'status': 'DRAFT',
        }
        resp = self.client.post(reverse('create_competition'), data)
        self.assertContains(resp, 'Select the competition category')
        self.assertFalse(Competition.objects.filter(name='NO CATEGORY').exists())

    def test_create_competition_cultural_requires_subtype(self):
        for event_type in ('', 'NOT_A_TYPE'):
            data = {
                'name': 'Cultural Only', 'description': 'desc',
                'start_date': '2026-02-01 00:00:00', 'end_date': '2026-02-02 00:00:00',
                'status': 'DRAFT', 'kind': 'CULTURAL', 'cultural_event_type': event_type,
            }
            resp = self.client.post(reverse('create_competition'), data)
            self.assertContains(resp, 'sub-type')
            self.assertFalse(Competition.objects.filter(name='CULTURAL ONLY').exists())

    def test_create_competition_sports_clears_cultural_subtype(self):
        data = {
            'name': 'Mislabeled', 'description': 'desc',
            'start_date': '2026-02-01 00:00:00', 'end_date': '2026-02-02 00:00:00',
            'status': 'DRAFT', 'kind': 'SPORTS', 'cultural_event_type': 'DANCE',
        }
        resp = self.client.post(reverse('create_competition'), data)
        self.assertRedirects(resp, reverse('competition_list'))
        comp = Competition.objects.get(name='MISLABELED')
        self.assertEqual(comp.kind, 'SPORTS')
        self.assertEqual(comp.cultural_event_type, '')

    def test_edit_competition_rejects_invalid_category_without_saving(self):
        resp = self.client.post(
            reverse('edit_competition', args=[self.competition.id]),
            {
                'title': 'Renamed', 'description': 'new',
                'start_date': '2026-03-01 00:00:00', 'end_date': '2026-03-02 00:00:00',
                'status': 'ACTIVE', 'kind': 'CULTURAL', 'cultural_event_type': '',
            },
        )
        self.assertContains(resp, 'sub-type')
        self.competition.refresh_from_db()
        self.assertEqual(self.competition.name, 'Comp')
        self.assertNotEqual(self.competition.kind, 'CULTURAL')

    def test_edit_competition_updates_medal_points(self):
        data = {
            'title': 'Comp', 'description': 'new',
            'start_date': '2026-03-01 00:00:00', 'end_date': '2026-03-02 00:00:00',
            'status': 'ACTIVE', 'kind': 'SPORTS',
            'gold_points': '20', 'silver_points': '10', 'bronze_points': '5',
        }
        self.client.post(reverse('edit_competition', args=[self.competition.id]), data)
        self.competition.refresh_from_db()
        self.assertEqual(self.competition.kind, 'SPORTS')
        self.assertEqual(self.competition.gold_points, Decimal('20'))
        self.assertEqual(self.competition.bronze_points, Decimal('5'))

    def test_create_round_saves_criterion_weights(self):
        data = {
            'name': 'R2', 'description': 'd', 'order': '2', 'weight_percentage': '0',
            'criterion_names[]': ['Creativity'], 'criterion_descriptions[]': ['x'],
            'criterion_max_scores[]': ['100'], 'criterion_weights[]': ['30'],
        }
        resp = self.client.post(reverse('create_round', args=[self.competition.id]), data)
        self.assertRedirects(resp, reverse('manage_rounds', args=[self.competition.id]))
        criterion = Criterion.objects.get(name='CREATIVITY')
        self.assertEqual(criterion.weight_percentage, Decimal('30'))

    def test_edit_round_without_criterion_payload_keeps_criteria(self):
        round_obj = Round.objects.create(
            competition=self.competition, name='R', description='d', order=1,
            status='PENDING', weight_percentage=Decimal('100'),
        )
        criterion = Criterion.objects.create(
            round=round_obj, name='Keep me', description='d', max_score=Decimal('100'),
        )
        data = {
            'name': 'Renamed', 'description': 'd', 'order': '1',
            'weight_percentage': '100',
        }
        self.client.post(reverse('edit_round', args=[self.competition.id, round_obj.id]), data)
        round_obj.refresh_from_db()
        self.assertEqual(round_obj.name, 'RENAMED')
        self.assertTrue(Criterion.objects.filter(id=criterion.id).exists())

    def test_edit_round_updates_criterion_weight(self):
        round_obj = Round.objects.create(
            competition=self.competition, name='R', description='d', order=1,
            status='PENDING', weight_percentage=Decimal('100'),
        )
        criterion = Criterion.objects.create(
            round=round_obj, name='C', description='d', max_score=Decimal('100'),
        )
        data = {
            'name': 'R', 'description': 'd', 'order': '1', 'weight_percentage': '100',
            'criterion_names[]': ['C'], 'criterion_descriptions[]': ['d'],
            'criterion_max_scores[]': ['100'], 'criterion_ids[]': [str(criterion.id)],
            'criterion_weights[]': ['25'],
        }
        self.client.post(reverse('edit_round', args=[self.competition.id, round_obj.id]), data)
        criterion.refresh_from_db()
        self.assertEqual(criterion.weight_percentage, Decimal('25'))


class SocioCulturalManagementTest(TestCase):
    """The cultural hub keeps socio-cultural competitions apart from sports."""

    def setUp(self):
        self.admin = User.objects.create_superuser('admin', 'a@a.com', 'pass')
        self.client.login(username='admin', password='pass')
        self.cultural = Competition.objects.create(
            name='Himig Campus', description='Solo singing',
            kind=Competition.Kind.CULTURAL,
            cultural_event_type=Competition.CulturalEventType.SINGING,
            status='ACTIVE',
            start_date='2026-01-01 00:00:00', end_date='2026-01-02 00:00:00',
            created_by=self.admin,
        )
        self.sports = Competition.objects.create(
            name='Intramurals', description='Ball games',
            kind=Competition.Kind.SPORTS,
            status='ACTIVE',
            start_date='2026-02-01 00:00:00', end_date='2026-02-02 00:00:00',
            created_by=self.admin,
        )

    def test_page_lists_only_cultural_competitions(self):
        response = self.client.get(reverse('socio_cultural_management'))
        self.assertEqual(response.status_code, 200)
        rows = response.context['cultural_competitions']
        self.assertEqual([c.id for c in rows], [self.cultural.id])
        self.assertContains(response, self.cultural.name)
        self.assertNotContains(response, self.sports.name)
        self.assertEqual(response.context['stats']['competitions'], 1)

    def test_event_type_filter(self):
        response = self.client.get(
            reverse('socio_cultural_management'), {'type': 'DANCE'},
        )
        self.assertEqual(response.context['selected_type'], 'DANCE')
        self.assertEqual(response.context['cultural_competitions'], [])

        response = self.client.get(
            reverse('socio_cultural_management'), {'type': 'SINGING'},
        )
        self.assertEqual(
            [c.id for c in response.context['cultural_competitions']],
            [self.cultural.id],
        )

    def test_malformed_type_is_ignored(self):
        response = self.client.get(
            reverse('socio_cultural_management'), {'type': 'NOT-A-TYPE'},
        )
        self.assertEqual(response.context['selected_type'], '')
        self.assertEqual(len(response.context['cultural_competitions']), 1)

    def test_page_requires_management_role(self):
        spectator = User.objects.create_user('culture_viewer', 'c@c.com', 'pass')
        profile, _ = UserProfile.objects.get_or_create(user=spectator)
        profile.role = UserProfile.Role.SPECTATOR
        profile.save()
        self.client.force_login(spectator)
        self.assertEqual(
            self.client.get(reverse('socio_cultural_management')).status_code, 403,
        )
