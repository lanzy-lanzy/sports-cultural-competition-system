from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from .models import Competition, Round, Criterion, CulturalMainType, CulturalSubType
from scoring.models import CompetitionResult
from sports.models import SportType, SportsEvent, Venue
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
        self.assertRedirects(
            resp, f"{reverse('competition_list')}?category=cultural",
        )
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

    def test_competition_list_defaults_to_sports_only(self):
        response = self.client.get(reverse('competition_list'))
        self.assertEqual(response.context['category'], 'sports')
        rows = list(response.context['page_obj'])
        self.assertEqual([c.id for c in rows], [self.sports.id])
        self.assertContains(response, self.sports.name)
        self.assertNotContains(response, self.cultural.name)
        self.assertEqual(response.context['sports_count'], 1)
        self.assertEqual(response.context['cultural_count'], 1)

    def test_competition_list_cultural_tab_lists_only_cultural(self):
        response = self.client.get(
            reverse('competition_list'), {'category': 'cultural'},
        )
        self.assertEqual(response.context['category'], 'cultural')
        rows = list(response.context['page_obj'])
        self.assertEqual([c.id for c in rows], [self.cultural.id])
        self.assertContains(response, self.cultural.name)
        self.assertNotContains(response, self.sports.name)

    def test_competition_list_unknown_category_falls_back_to_sports(self):
        response = self.client.get(
            reverse('competition_list'), {'category': 'not-a-category'},
        )
        self.assertEqual(response.context['category'], 'sports')
        rows = list(response.context['page_obj'])
        self.assertEqual([c.id for c in rows], [self.sports.id])


class CompetitionListFilterTest(TestCase):
    """The Competitions page groups each tab by sub-category and takes a
    free text search, both travelling in the query string."""

    def setUp(self):
        self.admin = User.objects.create_superuser('admin', 'a@a.com', 'pass')
        self.client.login(username='admin', password='pass')

        self.basketball = SportType.objects.create(name='Basketball')
        self.volleyball = SportType.objects.create(name='Volleyball')
        self.gym = Venue.objects.create(name='Main Gymnasium')

        self.hoops = Competition.objects.create(
            name='Intramural Basketball', description='Five a side',
            kind=Competition.Kind.SPORTS, status='ACTIVE',
            start_date='2026-01-01 00:00:00', end_date='2026-01-02 00:00:00',
            created_by=self.admin,
        )
        self.net = Competition.objects.create(
            name='Intramural Volleyball', description='Six a side',
            kind=Competition.Kind.SPORTS, status='ACTIVE',
            start_date='2026-02-01 00:00:00', end_date='2026-02-02 00:00:00',
            created_by=self.admin,
        )
        self.himig = Competition.objects.create(
            name='Himig Campus', description='Solo singing',
            kind=Competition.Kind.CULTURAL,
            cultural_event_type=Competition.CulturalEventType.SINGING,
            status='ACTIVE',
            start_date='2026-03-01 00:00:00', end_date='2026-03-02 00:00:00',
            created_by=self.admin,
        )
        self.latin = Competition.objects.create(
            name='Latin American Dance', description='Dance sport',
            kind=Competition.Kind.CULTURAL,
            cultural_event_type=Competition.CulturalEventType.DANCE,
            status='ACTIVE',
            start_date='2026-04-01 00:00:00', end_date='2026-04-02 00:00:00',
            created_by=self.admin,
        )
        SportsEvent.objects.create(
            competition=self.hoops, sport_type=self.basketball,
            name='Basketball - Open', venue=self.gym,
        )
        SportsEvent.objects.create(
            competition=self.net, sport_type=self.volleyball,
            name='Volleyball - Open',
        )

    def test_sports_tab_chips_group_by_sport_type(self):
        response = self.client.get(reverse('competition_list'))
        chips = response.context['subcategories']
        self.assertEqual([c['label'] for c in chips], ['Basketball', 'Volleyball'])
        self.assertEqual([c['count'] for c in chips], [1, 1])
        self.assertEqual(response.context['all_count'], 2)
        self.assertEqual(response.context['selected_sub'], '')
        self.assertFalse(response.context['is_filtered'])

    def test_sports_tab_chip_filters_to_one_discipline(self):
        response = self.client.get(
            reverse('competition_list'), {'sub': str(self.basketball.id)},
        )
        rows = list(response.context['page_obj'])
        self.assertEqual([c.id for c in rows], [self.hoops.id])
        self.assertEqual(response.context['selected_sub_label'], 'Basketball')
        self.assertTrue(response.context['is_filtered'])
        # The other chip stays reachable, so counters keep showing the tab.
        self.assertEqual(response.context['all_count'], 2)

    def test_cultural_tab_chips_group_by_event_type(self):
        response = self.client.get(
            reverse('competition_list'), {'category': 'cultural'},
        )
        chips = response.context['subcategories']
        self.assertEqual([c['value'] for c in chips], ['DANCE', 'SINGING'])
        self.assertEqual([c['label'] for c in chips],
                         ['Dancing', 'Singing'])

        response = self.client.get(
            reverse('competition_list'),
            {'category': 'cultural', 'sub': 'DANCE'},
        )
        rows = list(response.context['page_obj'])
        self.assertEqual([c.id for c in rows], [self.latin.id])

    def test_search_matches_name_sport_and_venue(self):
        expected = {
            'basketball': [self.hoops.id],
            'volley': [self.net.id],
            'gymnasium': [self.hoops.id],
            'five a': [self.hoops.id],
        }
        for term, ids in expected.items():
            with self.subTest(term=term):
                response = self.client.get(reverse('competition_list'), {'q': term})
                self.assertEqual([c.id for c in response.context['page_obj']], ids)
                self.assertEqual(response.context['query'], term)
                self.assertTrue(response.context['is_filtered'])

    def test_search_narrows_the_chip_counters(self):
        response = self.client.get(
            reverse('competition_list'), {'category': 'cultural', 'q': 'sing'},
        )
        chips = response.context['subcategories']
        self.assertEqual([c['value'] for c in chips], ['SINGING'])
        self.assertEqual(response.context['all_count'], 1)
        self.assertEqual(response.context['result_count'], 1)

    def test_search_and_subcategory_combine(self):
        response = self.client.get(
            reverse('competition_list'),
            {'category': 'cultural', 'q': 'latin', 'sub': 'DANCE'},
        )
        rows = list(response.context['page_obj'])
        self.assertEqual([c.id for c in rows], [self.latin.id])
        self.assertEqual(response.context['selected_sub'], 'DANCE')

    def test_unknown_subcategory_is_ignored(self):
        response = self.client.get(
            reverse('competition_list'), {'category': 'cultural', 'sub': 'NOT-A-TYPE'},
        )
        self.assertEqual(response.context['selected_sub'], '')
        self.assertEqual(len(response.context['page_obj']), 2)

        response = self.client.get(reverse('competition_list'), {'sub': '999999'})
        self.assertEqual(response.context['selected_sub'], '')
        self.assertEqual(len(response.context['page_obj']), 2)

    def test_spectator_only_sees_published_competitions(self):
        spectator = User.objects.create_user('viewer', 'v@v.com', 'pass')
        profile, _ = UserProfile.objects.get_or_create(user=spectator)
        profile.role = UserProfile.Role.SPECTATOR
        profile.save()
        Competition.objects.create(
            name='Draft Ball Games', description='hidden',
            kind=Competition.Kind.SPORTS, status='DRAFT',
            start_date='2026-05-01 00:00:00', end_date='2026-05-02 00:00:00',
            created_by=self.admin,
        )
        self.client.force_login(spectator)
        response = self.client.get(reverse('competition_list'), {'q': 'ball'})
        rows = list(response.context['page_obj'])
        self.assertNotIn('Draft Ball Games', [c.name for c in rows])
        self.assertEqual(response.context['sports_count'], 2)


class CulturalSubtypeTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser('admin', 'a@a.com', 'pass')
        self.client.login(username='admin', password='pass')

    def _add_subtype(self, **overrides):
        data = {'name': 'Folk Dance', 'main_type': '__new__', 'new_main_type': 'Sayaw'}
        data.update(overrides)
        return self.client.post(reverse('add_cultural_subtype'), data)

    def test_seeded_taxonomy_matches_legacy_choices(self):
        for slug in Competition.CulturalEventType.values:
            self.assertTrue(CulturalSubType.objects.filter(slug=slug).exists(), slug)

    def test_add_subtype_creates_new_main_group(self):
        resp = self._add_subtype()
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data['slug'], 'FOLK_DANCE')
        self.assertEqual(data['name'], 'Folk Dance')
        self.assertEqual(data['main_type'], 'Sayaw')
        subtype = CulturalSubType.objects.get(slug='FOLK_DANCE')
        self.assertEqual(subtype.main_type.name, 'Sayaw')

    def test_add_subtype_under_existing_main_group(self):
        main = CulturalMainType.objects.get(name='Performing Arts')
        resp = self._add_subtype(name='Cheerdance', main_type=str(main.id), new_main_type='')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()['main_type'], 'Performing Arts')
        self.assertEqual(CulturalSubType.objects.get(slug='CHEERDANCE').main_type_id, main.id)

    def test_add_subtype_reuses_existing_name_or_slug(self):
        before = CulturalSubType.objects.count()
        main = CulturalMainType.objects.get(name='Performing Arts')
        # Same display name as the seeded "Dancing" (slug DANCE).
        resp = self._add_subtype(name='dancing', main_type=str(main.id), new_main_type='')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()['slug'], 'DANCE')
        # Different name that collides with the seeded slug.
        resp = self._add_subtype(name='Dance', main_type=str(main.id), new_main_type='')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()['slug'], 'DANCE')
        self.assertEqual(CulturalSubType.objects.count(), before)

    def test_add_subtype_new_main_group_name_matching_is_case_insensitive(self):
        resp = self._add_subtype(name='Hip Hop', new_main_type='performing arts')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()['main_type'], 'Performing Arts')
        self.assertEqual(CulturalMainType.objects.count(), 3)

    def test_add_subtype_validates_input(self):
        self.assertEqual(self._add_subtype(name='').status_code, 400)
        self.assertEqual(self._add_subtype(name='   ').status_code, 400)
        self.assertEqual(self._add_subtype(name='!!!').status_code, 400)
        self.assertEqual(self._add_subtype(new_main_type='').status_code, 400)
        self.assertEqual(
            self._add_subtype(main_type='999999', new_main_type='').status_code, 400,
        )
        self.assertFalse(CulturalSubType.objects.filter(name='!!!').exists())

    def test_add_subtype_requires_management_role(self):
        spectator = User.objects.create_user('viewer', 'v@v.com', 'pass')
        profile, _ = UserProfile.objects.get_or_create(user=spectator)
        profile.role = UserProfile.Role.SPECTATOR
        profile.save()
        self.client.force_login(spectator)
        resp = self._add_subtype()
        self.assertEqual(resp.status_code, 403)

    def test_create_competition_with_new_subtype(self):
        self._add_subtype()
        data = {
            'name': 'Sayaw Festival', 'description': 'desc',
            'start_date': '2026-02-01 00:00:00', 'end_date': '2026-02-02 00:00:00',
            'status': 'DRAFT', 'kind': 'CULTURAL', 'cultural_event_type': 'FOLK_DANCE',
            'round_names[]': ['Finals'], 'round_orders[]': ['1'],
            'round_weights[]': ['100'], 'round_statuses[]': ['PENDING'],
            'criterion_names_1[]': ['Choreography'], 'criterion_descriptions_1[]': ['x'],
            'criterion_max_scores_1[]': ['100'],
        }
        resp = self.client.post(reverse('create_competition'), data)
        self.assertRedirects(resp, f"{reverse('competition_list')}?category=cultural")
        comp = Competition.objects.get(name='SAYAW FESTIVAL')
        self.assertEqual(comp.cultural_event_type, 'FOLK_DANCE')
        self.assertEqual(comp.get_cultural_event_type_display(), 'Folk Dance')

    def test_new_subtype_appears_in_create_and_edit_forms(self):
        self._add_subtype()
        resp = self.client.get(reverse('create_competition'))
        self.assertContains(resp, 'Folk Dance')
        self.assertContains(resp, 'Sayaw')

        comp = Competition.objects.create(
            name='Sayaw Festival', description='d', kind=Competition.Kind.CULTURAL,
            cultural_event_type='FOLK_DANCE', status='DRAFT',
            start_date='2026-02-01 00:00:00', end_date='2026-02-02 00:00:00',
            created_by=self.admin,
        )
        resp = self.client.get(reverse('edit_competition', args=[comp.id]))
        self.assertContains(resp, '<option value="FOLK_DANCE" selected>Folk Dance</option>')

    def test_list_page_modals_include_new_subtype(self):
        self._add_subtype()
        resp = self.client.get(reverse('competition_list'), {'category': 'cultural'})
        self.assertContains(resp, 'id="m-cultural_event_type"')
        self.assertContains(resp, 'id="edit-cultural_event_type"')
        self.assertContains(resp, 'id="m-subtype-add-toggle"')
        self.assertContains(resp, 'id="edit-subtype-add-toggle"')
        self.assertContains(resp, 'Folk Dance')
        self.assertContains(resp, 'Sayaw')

    def test_list_and_management_pages_use_new_subtype_label(self):
        comp = Competition.objects.create(
            name='Sayaw Festival', description='d', kind=Competition.Kind.CULTURAL,
            cultural_event_type='FOLK_DANCE', status='ACTIVE',
            start_date='2026-02-01 00:00:00', end_date='2026-02-02 00:00:00',
            created_by=self.admin,
        )
        resp = self.client.get(reverse('competition_list'), {'category': 'cultural'})
        chips = resp.context['subcategories']
        self.assertEqual([c['label'] for c in chips], ['Folk Dance'])

        resp = self.client.get(reverse('socio_cultural_management'))
        self.assertContains(resp, 'Folk Dance')
        resp = self.client.get(reverse('socio_cultural_management'), {'type': 'FOLK_DANCE'})
        self.assertEqual([c.id for c in resp.context['cultural_competitions']], [comp.id])

    def _edit_subtype(self, subtype, **overrides):
        data = {'id': str(subtype.id), 'name': subtype.name, 'main_type': str(subtype.main_type_id)}
        data.update(overrides)
        return self.client.post(reverse('edit_cultural_subtype'), data)

    def test_edit_subtype_renames_but_keeps_slug(self):
        subtype = CulturalSubType.objects.get(slug='DANCE')
        comp = Competition.objects.create(
            name='Dance Fest', description='d', kind=Competition.Kind.CULTURAL,
            cultural_event_type='DANCE', status='DRAFT',
            start_date='2026-02-01 00:00:00', end_date='2026-02-02 00:00:00',
            created_by=self.admin,
        )
        resp = self._edit_subtype(subtype, name='Modern Dance')
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data['slug'], 'DANCE')
        self.assertEqual(data['name'], 'Modern Dance')
        subtype.refresh_from_db()
        self.assertEqual(subtype.slug, 'DANCE')
        self.assertEqual(comp.get_cultural_event_type_display(), 'Modern Dance')

    def test_edit_subtype_moves_to_another_main_group(self):
        subtype = CulturalSubType.objects.get(slug='DANCE')
        other = CulturalMainType.objects.get(name='Other')
        resp = self._edit_subtype(subtype, main_type=str(other.id))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()['main_type'], 'Other')
        subtype.refresh_from_db()
        self.assertEqual(subtype.main_type_id, other.id)
        self.assertEqual(subtype.slug, 'DANCE')

    def test_edit_subtype_rejects_duplicate_name_or_slug(self):
        subtype = CulturalSubType.objects.get(slug='DANCE')
        # Case-insensitive clash with the seeded "Singing" display name.
        self.assertEqual(self._edit_subtype(subtype, name='singing').status_code, 400)
        # New name whose slug collides with the seeded ESSAY_WRITING slug.
        self.assertEqual(self._edit_subtype(subtype, name='Essay Writing').status_code, 400)
        subtype.refresh_from_db()
        self.assertEqual(subtype.name, 'Dancing')

    def test_edit_subtype_validates_input(self):
        subtype = CulturalSubType.objects.get(slug='DANCE')
        self.assertEqual(self._edit_subtype(subtype, id='999999').status_code, 404)
        self.assertEqual(self._edit_subtype(subtype, id='abc').status_code, 404)
        self.assertEqual(self._edit_subtype(subtype, name='').status_code, 400)
        self.assertEqual(self._edit_subtype(subtype, name='x' * 101).status_code, 400)
        self.assertEqual(self._edit_subtype(subtype, main_type='999999').status_code, 400)

    def test_delete_unused_subtype(self):
        self._add_subtype()
        subtype = CulturalSubType.objects.get(slug='FOLK_DANCE')
        resp = self.client.post(reverse('delete_cultural_subtype'), {'id': str(subtype.id)})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json(), {'deleted': True, 'id': subtype.id, 'slug': 'FOLK_DANCE'})
        self.assertFalse(CulturalSubType.objects.filter(slug='FOLK_DANCE').exists())

    def test_delete_subtype_blocked_when_in_use(self):
        subtype = CulturalSubType.objects.get(slug='DANCE')
        Competition.objects.create(
            name='Dance Fest', description='d', kind=Competition.Kind.CULTURAL,
            cultural_event_type='DANCE', status='DRAFT',
            start_date='2026-02-01 00:00:00', end_date='2026-02-02 00:00:00',
            created_by=self.admin,
        )
        resp = self.client.post(reverse('delete_cultural_subtype'), {'id': str(subtype.id)})
        self.assertEqual(resp.status_code, 400)
        self.assertIn('1 competition(s) still use it', resp.json()['error'])
        self.assertTrue(CulturalSubType.objects.filter(slug='DANCE').exists())

    def test_edit_main_group_renames(self):
        main = CulturalMainType.objects.get(name='Performing Arts')
        resp = self.client.post(reverse('edit_cultural_main_type'),
                                {'id': str(main.id), 'name': 'Stage Arts'})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()['name'], 'Stage Arts')
        main.refresh_from_db()
        self.assertEqual(main.name, 'Stage Arts')

    def test_edit_main_group_validates_input(self):
        main = CulturalMainType.objects.get(name='Other')
        performing = CulturalMainType.objects.get(name='Performing Arts')
        resp = self.client.post(reverse('edit_cultural_main_type'),
                                {'id': str(main.id), 'name': 'performing arts'})
        self.assertEqual(resp.status_code, 400)
        resp = self.client.post(reverse('edit_cultural_main_type'),
                                {'id': str(main.id), 'name': ''})
        self.assertEqual(resp.status_code, 400)
        resp = self.client.post(reverse('edit_cultural_main_type'),
                                {'id': '999999', 'name': 'X'})
        self.assertEqual(resp.status_code, 404)
        main.refresh_from_db()
        self.assertEqual(main.name, 'Other')
        self.assertTrue(CulturalMainType.objects.filter(id=performing.id).exists())

    def test_delete_empty_main_group(self):
        main = CulturalMainType.objects.create(name='Temporary Group')
        resp = self.client.post(reverse('delete_cultural_main_type'), {'id': str(main.id)})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json(), {'deleted': True, 'id': main.id})
        self.assertFalse(CulturalMainType.objects.filter(name='Temporary Group').exists())

    def test_delete_main_group_with_subtypes_blocked(self):
        main = CulturalMainType.objects.get(name='Performing Arts')
        resp = self.client.post(reverse('delete_cultural_main_type'), {'id': str(main.id)})
        self.assertEqual(resp.status_code, 400)
        self.assertIn('still has sub-types', resp.json()['error'])
        self.assertTrue(CulturalMainType.objects.filter(id=main.id).exists())

    def test_edit_delete_endpoints_require_management_role(self):
        spectator = User.objects.create_user('viewer2', 'v2@v.com', 'pass')
        profile, _ = UserProfile.objects.get_or_create(user=spectator)
        profile.role = UserProfile.Role.SPECTATOR
        profile.save()
        self.client.force_login(spectator)
        subtype = CulturalSubType.objects.get(slug='DANCE')
        main = CulturalMainType.objects.get(name='Other')
        for url, data in [
            (reverse('edit_cultural_subtype'), {'id': str(subtype.id), 'name': 'X', 'main_type': str(main.id)}),
            (reverse('delete_cultural_subtype'), {'id': str(subtype.id)}),
            (reverse('edit_cultural_main_type'), {'id': str(main.id), 'name': 'X'}),
            (reverse('delete_cultural_main_type'), {'id': str(main.id)}),
        ]:
            self.assertEqual(self.client.post(url, data).status_code, 403, url)

    def test_manage_panel_renders_in_forms(self):
        Competition.objects.create(
            name='Dance Fest', description='d', kind=Competition.Kind.CULTURAL,
            cultural_event_type='DANCE', status='DRAFT',
            start_date='2026-02-01 00:00:00', end_date='2026-02-02 00:00:00',
            created_by=self.admin,
        )
        resp = self.client.get(reverse('create_competition'))
        self.assertContains(resp, 'id="subtype-manage-panel"')
        self.assertContains(resp, 'id="subtype-manage-toggle"')
        self.assertContains(resp, 'id="manage-group-template"')
        self.assertContains(resp, 'id="manage-sub-template"')
        self.assertContains(resp, 'Used by 1')
        self.assertContains(resp, 'Unused')

        resp = self.client.get(reverse('competition_list'), {'category': 'cultural'})
        self.assertContains(resp, 'id="m-subtype-manage-toggle"')
        self.assertContains(resp, 'id="edit-subtype-manage-toggle"')
        self.assertContains(resp, 'id="m-subtype-manage-panel"')
        self.assertContains(resp, 'id="edit-subtype-manage-panel"')
