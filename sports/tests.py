from collections import defaultdict
from datetime import date
from decimal import Decimal
import re

from django.contrib.auth.models import User
from django.core.management import call_command
from django.db.models import Count
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import UserProfile
from competitions.models import Competition
from participants.models import Participant
from teams.models import Team, TeamMembership, TeamStaff
from .management.commands.seed_sports import EVENT_SPECS
from .models import EventEntry, Match, MatchEntry, SportsEvent, SportType, Venue
from .services import (
    compute_elimination_standings,
    compute_group_stage_standings,
    compute_standings,
    find_venue_conflicts,
    generate_bracket,
    match_overview,
    record_match_result,
)


class SportsModelTest(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser('admin', 'admin@example.com', 'pass')
        self.competition = Competition.objects.create(
            name='Sports Meet',
            description='Annual sports meet',
            start_date='2026-03-01T08:00:00Z',
            end_date='2026-03-05T17:00:00Z',
            status='ACTIVE',
            created_by=self.admin,
        )
        self.sport = SportType.objects.create(name='Basketball', team_based=True)
        self.event = SportsEvent.objects.create(
            competition=self.competition,
            sport_type=self.sport,
            name='Basketball - Men',
            team_based=True,
            format=SportsEvent.Format.ROUND_ROBIN,
        )
        self.team_a = Team.objects.create(name='Team A', category=Team.Category.SPORTS, created_by=self.admin)
        self.team_b = Team.objects.create(name='Team B', category=Team.Category.SPORTS, created_by=self.admin)

    def test_event_requires_contestant_type(self):
        with self.assertRaises(Exception):
            EventEntry.objects.create(event=self.event, team=None, participant=None)

    def test_unique_team_entry(self):
        EventEntry.objects.create(event=self.event, team=self.team_a)
        with self.assertRaises(Exception):
            EventEntry.objects.create(event=self.event, team=self.team_a)

    def test_entry_display_name_and_seed(self):
        entry = EventEntry.objects.create(event=self.event, team=self.team_a)
        self.assertEqual(entry.display_name, 'Team A')
        self.assertEqual(entry.seed, 1)
        second = EventEntry.objects.create(event=self.event, team=self.team_b)
        self.assertEqual(second.seed, 2)

    def test_match_entry_result(self):
        entry_a = EventEntry.objects.create(event=self.event, team=self.team_a, status='CONFIRMED')
        entry_b = EventEntry.objects.create(event=self.event, team=self.team_b, status='CONFIRMED')
        generate_bracket(self.event)
        match = self.event.matches.first()
        self.assertEqual(match.entries.count(), 2)
        record_match_result(match, {1: 21, 2: 15})
        match.refresh_from_db()
        self.assertEqual(match.status, Match.Status.COMPLETED)
        self.assertEqual(match.winner.team, self.team_a)
        self.assertEqual(match.winner.score, 21)


class SingleEliminationBracketTest(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser('admin', 'admin@example.com', 'pass')
        self.competition = Competition.objects.create(
            name='Sports Meet',
            description='Annual sports meet',
            start_date='2026-03-01T08:00:00Z',
            end_date='2026-03-05T17:00:00Z',
            status='ACTIVE',
            created_by=self.admin,
        )
        self.sport = SportType.objects.create(name='Basketball', team_based=True)
        self.event = SportsEvent.objects.create(
            competition=self.competition,
            sport_type=self.sport,
            name='Basketball - Men',
            team_based=True,
            format=SportsEvent.Format.SINGLE_ELIMINATION,
        )
        self.teams = []
        for i in range(8):
            team = Team.objects.create(name=f'Team {i + 1}', category=Team.Category.SPORTS, created_by=self.admin)
            self.teams.append(team)
            EventEntry.objects.create(event=self.event, team=team, status='CONFIRMED')

    def test_bracket_structure(self):
        generate_bracket(self.event)
        self.assertEqual(self.event.matches.count(), 7)  # 8-team single elimination
        rounds = match_overview(self.event)
        self.assertEqual(len(rounds), 3)  # QF, SF, F
        self.assertEqual(len(rounds[1]), 4)
        self.assertEqual(len(rounds[2]), 2)
        self.assertEqual(len(rounds[3]), 1)

    def test_winner_advances(self):
        generate_bracket(self.event)
        first_round = match_overview(self.event)[1]
        record_match_result(first_round[0], {1: 10, 2: 8})
        semifinal = first_round[0].next_match
        self.assertEqual(semifinal.entries.count(), 1)
        self.assertEqual(semifinal.entries.first().team, self.teams[0])

    def test_byes_for_non_power_of_two(self):
        self.event.entries.all().delete()
        for i in range(5):
            team = Team.objects.create(name=f'Five {i}', category=Team.Category.SPORTS, created_by=self.admin)
            EventEntry.objects.create(event=self.event, team=team, status='CONFIRMED')
        generate_bracket(self.event)
        # 5 teams -> bracket of 8 -> 4 first-round matches, some with byes
        self.assertEqual(self.event.matches.count(), 7)
        # 3 bye-winners advance into round 2 (the 4th slot awaits the live match winner)
        round_two = self.event.matches.filter(round_number=2)
        total_round_two_entries = sum(m.entries.count() for m in round_two)
        self.assertEqual(total_round_two_entries, 3)


class RoundRobinStandingsTest(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser('admin', 'admin@example.com', 'pass')
        self.competition = Competition.objects.create(
            name='Sports Meet',
            description='Annual sports meet',
            start_date='2026-03-01T08:00:00Z',
            end_date='2026-03-05T17:00:00Z',
            status='ACTIVE',
            created_by=self.admin,
        )
        self.sport = SportType.objects.create(name='Volleyball', team_based=True)
        self.event = SportsEvent.objects.create(
            competition=self.competition,
            sport_type=self.sport,
            name='Volleyball',
            team_based=True,
            format=SportsEvent.Format.ROUND_ROBIN,
        )
        self.teams = []
        for i in range(4):
            team = Team.objects.create(name=f'Team {i + 1}', category=Team.Category.SPORTS, created_by=self.admin)
            self.teams.append(team)
            EventEntry.objects.create(event=self.event, team=team, status='CONFIRMED')

    def test_round_robin_matches(self):
        generate_bracket(self.event)
        self.assertEqual(self.event.matches.count(), 6)  # 4 teams, each pair once

    def test_standings_ranking(self):
        generate_bracket(self.event)
        matches = list(self.event.matches.all().order_by('id'))
        # Pairings (circle method, 4 teams): R1: T1-T4, T2-T3; R2: T1-T3, T4-T2; R3: T1-T2, T3-T4
        results = [
            {1: 25, 2: 20}, {1: 25, 2: 18},   # R1: T1 beats T4, T2 beats T3
            {1: 25, 2: 22}, {1: 25, 2: 10},   # R2: T1 beats T3, T4 beats T2
            {1: 25, 2: 15}, {1: 25, 2: 18},   # R3: T1 beats T2, T3 beats T4
        ]
        for match, score_map in zip(matches, results):
            record_match_result(match, score_map)
        standings = compute_standings(self.event)
        self.assertEqual(standings[0]['name'], 'Team 1')  # won all three
        self.assertEqual(standings[0]['wins'], 3)
        self.assertEqual(standings[0]['total_points'], 9)
        self.assertEqual(len(standings), 4)


class SportsViewsTest(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser('admin', 'admin@example.com', 'pass')
        self.competition = Competition.objects.create(
            name='Sports Meet',
            description='Annual sports meet',
            start_date='2026-03-01T08:00:00Z',
            end_date='2026-03-05T17:00:00Z',
            status='ACTIVE',
            created_by=self.admin,
        )
        self.sport = SportType.objects.create(name='Chess', team_based=False)

    def test_sport_type_crud_pages(self):
        self.client.force_login(self.admin)
        self.assertEqual(self.client.get(reverse('sport_type_list')).status_code, 200)
        response = self.client.post(reverse('sport_type_create'), {
            'name': 'Badminton', 'team_based': 'on', 'is_active': 'on',
        })
        self.assertRedirects(response, reverse('sport_type_list'))
        self.assertTrue(SportType.objects.filter(name='Badminton').exists())

    def test_venue_crud_pages(self):
        self.client.force_login(self.admin)
        self.assertEqual(self.client.get(reverse('venue_list')).status_code, 200)
        response = self.client.post(reverse('venue_create'), {
            'name': 'Main Gym', 'location': 'Campus', 'capacity': 500, 'is_active': 'on',
        })
        self.assertRedirects(response, reverse('venue_list'))
        self.assertTrue(Venue.objects.filter(name='Main Gym').exists())

    def test_event_creation_and_entries(self):
        self.client.force_login(self.admin)
        url = reverse('create_sport_event', args=[self.competition.id])
        response = self.client.post(url, {
            'sport_type': self.sport.id,
            'name': 'Chess Open',
            'category': 'OPEN',
            'gender': 'open',
            'team_based': 'off',
            'format': 'SINGLE_ELIMINATION',
            'max_teams': '16',
            'status': 'PLANNED',
        })
        event = SportsEvent.objects.get(name='Chess Open')
        self.assertRedirects(response, reverse('sport_event_detail', args=[event.id]))

        participant = Participant.objects.create(
            name='Alice', email='alice@example.com', phone='0917', age=20,
            gender='female', status='ACTIVE',
        )
        response = self.client.post(reverse('add_event_entry', args=[event.id]), {
            'contestant_type': 'participant',
            'participant': participant.id,
        })
        self.assertRedirects(response, reverse('sport_event_detail', args=[event.id]))
        self.assertTrue(event.entries.filter(participant=participant).exists())

    def test_spectator_cannot_access_sports(self):
        spectator = User.objects.create_user('viewer', 'viewer@example.com', 'pass')
        self.client.force_login(spectator)
        self.assertEqual(self.client.get(reverse('sport_type_list')).status_code, 403)

    def test_bracket_generation_requires_confirmed_entries(self):
        self.client.force_login(self.admin)
        self.event = SportsEvent.objects.create(
            competition=self.competition,
            sport_type=self.sport,
            name='Chess Open',
            team_based=False,
            format=SportsEvent.Format.SINGLE_ELIMINATION,
        )
        response = self.client.post(reverse('generate_event_bracket', args=[self.event.id]))
        self.assertRedirects(response, reverse('sport_event_detail', args=[self.event.id]))
        self.assertEqual(self.event.matches.count(), 0)


class RecordResultModalTest(TestCase):
    """Recording a match result happens in a single shared modal dialog."""

    @classmethod
    def setUpTestData(cls):
        call_command('seed_sports', quiet=True)
        cls.admin = User.objects.get(username='admin')

    def setUp(self):
        self.client.force_login(self.admin)

    def playable_match(self):
        return (
            Match.objects
            .exclude(status=Match.Status.COMPLETED)
            .annotate(entry_count=Count('entries'))
            .filter(entry_count=2)
            .order_by('id')
            .first()
        )

    def schedule_html(self, event):
        response = self.client.get(reverse('match_schedule', args=[event.id]))
        self.assertEqual(response.status_code, 200)
        return response.content.decode()

    def test_one_modal_per_page_not_per_match(self):
        event = self.playable_match().event
        html = self.schedule_html(event)
        self.assertEqual(html.count('id="result-modal"'), 1)
        self.assertEqual(html.count('id="result-modal-form"'), 1)

    def test_inline_toggle_form_is_gone(self):
        event = self.playable_match().event
        html = self.schedule_html(event)
        self.assertNotIn('toggleResult', html)
        self.assertNotIn('result-form-', html)

    def test_modal_posts_the_field_names_the_view_reads(self):
        event = self.playable_match().event
        html = self.schedule_html(event)
        for field in ('score_1', 'score_2', 'notes'):
            self.assertIn('name="{}"'.format(field), html)

    def test_every_playable_match_gets_one_trigger(self):
        """One modal, but a trigger button per match that still needs a result."""
        for event in SportsEvent.objects.order_by('id'):
            expected = list(
                Match.objects
                .filter(event=event)
                .exclude(status=Match.Status.COMPLETED)
                .annotate(entry_count=Count('entries'))
                .filter(entry_count=2)
                .values_list('id', flat=True)
            )
            html = self.schedule_html(event)
            triggers = re.findall(r'<button[^>]*\sdata-result-open\b', html, re.S)
            self.assertEqual(
                len(triggers), len(expected),
                '{} shows {} triggers for {} playable matches'.format(
                    event.name, len(triggers), len(expected)),
            )

    def test_trigger_carries_the_context_the_modal_shows(self):
        match = self.playable_match()
        html = self.schedule_html(match.event)
        trigger = re.search(r'<button[^>]*\sdata-result-open\b[^>]*>', html, re.S).group(0)
        self.assertIn('data-url="{}"'.format(reverse('record_match_result', args=[match.id])), trigger)
        self.assertIn('data-label="{}"'.format(match.label), trigger)
        for entry in match.entries.order_by('side'):
            self.assertIn('data-side{}="{}"'.format(entry.side, entry.display_name), trigger)

    def test_completed_matches_have_no_trigger(self):
        match = Match.objects.filter(status=Match.Status.COMPLETED).first()
        html = self.schedule_html(match.event)
        row = next(
            r for r in re.findall(r'<tr[^>]*>(.*?)</tr>', html, re.S)
            if 'data-url="{}"'.format(reverse('record_match_result', args=[match.id])) in r
        ) if reverse('record_match_result', args=[match.id]) in html else None
        if row is not None:
            self.assertNotIn('data-result-open', row)

    def test_modal_starts_closed_and_locks_scroll(self):
        html = self.schedule_html(self.playable_match().event)
        tag = re.search(r'<div id="result-modal"[^>]*>', html).group(0)
        classes = re.search(r'class="([^"]*)"', tag).group(1).split()
        self.assertIn('hidden', classes, 'modal is not hidden by default')
        self.assertNotIn('flex', classes, 'modal is visible by default')
        # Stacked above the sidebar (z-50) so it is never clipped.
        self.assertRegex(tag, r'z-\[(?:[6-9]|\d{2,})\]')
        self.assertIn("document.body.style.overflow = 'hidden'", html)
        self.assertIn('document.body.style.overflow = previousOverflow', html)

    def test_modal_supports_keyboard_and_backdrop_close(self):
        html = self.schedule_html(self.playable_match().event)
        self.assertIn("event.key === 'Escape'", html)
        self.assertIn('data-result-close', html)
        self.assertIn('lastFocused', html)

    def test_submitting_the_modal_records_the_result(self):
        match = self.playable_match()
        entries = list(match.entries.order_by('side'))
        self.client.post(
            reverse('record_match_result', args=[match.id]),
            {'score_1': '11', 'score_2': '7', 'notes': 'Recorded from the modal.'},
        )
        match.refresh_from_db()
        self.assertEqual(match.status, Match.Status.COMPLETED)
        self.assertEqual(match.notes, 'Recorded from the modal.')

        by_side = {e.side: e for e in match.entries.all()}
        self.assertEqual(by_side[entries[0].side].score, Decimal('11.00'))
        self.assertEqual(by_side[entries[1].side].score, Decimal('7.00'))
        self.assertTrue(by_side[entries[0].side].is_winner)
        self.assertFalse(by_side[entries[1].side].is_winner)


class DoubleEliminationBracketTest(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser('admin', 'admin@example.com', 'pass')
        self.competition = Competition.objects.create(
            name='Sports Meet', description='Annual sports meet',
            start_date='2026-03-01T08:00:00Z', end_date='2026-03-05T17:00:00Z',
            status='ACTIVE', created_by=self.admin,
        )
        self.sport = SportType.objects.create(name='Basketball', team_based=True)
        self.event = SportsEvent.objects.create(
            competition=self.competition, sport_type=self.sport,
            name='Basketball - Men', team_based=True,
            format=SportsEvent.Format.DOUBLE_ELIMINATION,
        )
        self.teams = []
        for i in range(4):
            team = Team.objects.create(name=f'Team {i + 1}', category=Team.Category.SPORTS, created_by=self.admin)
            self.teams.append(team)
            EventEntry.objects.create(event=self.event, team=team, status='CONFIRMED')

    def test_non_power_of_two_entries_rejected(self):
        self.event.entries.all().delete()
        for i in range(3):
            team = Team.objects.create(name=f'Odd {i}', category=Team.Category.SPORTS, created_by=self.admin)
            EventEntry.objects.create(event=self.event, team=team, status='CONFIRMED')
        with self.assertRaises(ValueError):
            generate_bracket(self.event)

    def test_bracket_structure(self):
        generate_bracket(self.event)
        # 4 teams: 2 WB rounds + 2 LB rounds + grand final = 6 matches
        self.assertEqual(self.event.matches.count(), 6)
        self.assertTrue(self.event.matches.filter(name='Grand Final').exists())
        self.assertEqual(self.event.matches.filter(round_number=1).count(), 2)
        self.assertEqual(self.event.matches.filter(round_number=3).count(), 1)
        self.assertEqual(self.event.matches.filter(round_number=5).count(), 1)

    def test_full_flow_determines_champion(self):
        generate_bracket(self.event)
        overview = match_overview(self.event)
        # Play every bracket match in round order.
        for round_no in sorted(overview):
            for match in overview[round_no]:
                entries = list(match.entries.all())
                if len(entries) != 2:
                    continue
                record_match_result(match, {1: 5, 2: 3})
        standings = compute_elimination_standings(self.event)
        champions = [row for row in standings if row['is_champion']]
        self.assertEqual(len(champions), 1)
        # The grand final winner is champion and ranks first.
        self.assertEqual(standings[0]['rank'], 1)
        self.assertEqual(standings[0]['name'], champions[0]['name'])


class GroupStageTest(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser('admin', 'admin@example.com', 'pass')
        self.competition = Competition.objects.create(
            name='Sports Meet', description='Annual sports meet',
            start_date='2026-03-01T08:00:00Z', end_date='2026-03-05T17:00:00Z',
            status='ACTIVE', created_by=self.admin,
        )
        self.sport = SportType.objects.create(name='Volleyball', team_based=True)
        self.event = SportsEvent.objects.create(
            competition=self.competition, sport_type=self.sport,
            name='Volleyball', team_based=True,
            format=SportsEvent.Format.GROUP_STAGE,
        )
        self.teams = []
        for i in range(8):
            team = Team.objects.create(name=f'Team {i + 1}', category=Team.Category.SPORTS, created_by=self.admin)
            self.teams.append(team)
            EventEntry.objects.create(event=self.event, team=team, status='CONFIRMED')

    def test_group_matches_created_with_group_labels(self):
        generate_bracket(self.event)
        group_matches = self.event.matches.filter(group__isnull=False)
        self.assertTrue(group_matches.exists())
        self.assertEqual(group_matches.values('group').distinct().count(), 2)

    def test_knockout_generated_when_groups_complete(self):
        generate_bracket(self.event)
        self.assertFalse(self.event.matches.filter(round_number__gt=1).exists())
        for match in self.event.matches.filter(group__isnull=False):
            record_match_result(match, {1: 25, 2: 20})
        self.assertTrue(self.event.matches.filter(round_number__gt=1).exists())
        group_stage = compute_group_stage_standings(self.event)
        self.assertIsNotNone(group_stage['knockout'])
        # Top 2 per group qualify.
        qualifiers = [row for group in group_stage['groups'] for row in group['rows'] if row['qualifies']]
        self.assertEqual(len(qualifiers), 4)


class VenueConflictTest(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser('admin', 'admin@example.com', 'pass')
        self.competition = Competition.objects.create(
            name='Sports Meet', description='d',
            start_date='2026-03-01T08:00:00Z', end_date='2026-03-05T17:00:00Z',
            status='ACTIVE', created_by=self.admin,
        )
        self.sport = SportType.objects.create(name='Basketball', team_based=True)
        self.event = SportsEvent.objects.create(
            competition=self.competition, sport_type=self.sport,
            name='Basketball', team_based=True,
            format=SportsEvent.Format.ROUND_ROBIN,
        )
        self.team_a = Team.objects.create(name='Team A', category=Team.Category.SPORTS, created_by=self.admin)
        self.team_b = Team.objects.create(name='Team B', category=Team.Category.SPORTS, created_by=self.admin)
        self.venue = Venue.objects.create(name='Main Gym', location='Campus', capacity=500, is_active=True)

    def test_overlapping_schedule_detected(self):
        from datetime import datetime
        from django.utils import timezone

        match = Match.objects.create(
            event=self.event,
            scheduled_start=timezone.make_aware(datetime(2026, 3, 2, 8, 0)),
            scheduled_end=timezone.make_aware(datetime(2026, 3, 2, 10, 0)),
            venue=self.venue,
            status=Match.Status.SCHEDULED,
        )
        conflicts = find_venue_conflicts(
            self.venue,
            timezone.make_aware(datetime(2026, 3, 2, 9, 0)),
            timezone.make_aware(datetime(2026, 3, 2, 11, 0)),
        )
        self.assertEqual(conflicts, [match])

    def test_non_overlapping_schedule_clear(self):
        from datetime import datetime
        from django.utils import timezone

        Match.objects.create(
            event=self.event,
            scheduled_start=timezone.make_aware(datetime(2026, 3, 2, 8, 0)),
            scheduled_end=timezone.make_aware(datetime(2026, 3, 2, 10, 0)),
            venue=self.venue,
            status=Match.Status.SCHEDULED,
        )
        conflicts = find_venue_conflicts(
            self.venue,
            timezone.make_aware(datetime(2026, 3, 2, 11, 0)),
            timezone.make_aware(datetime(2026, 3, 2, 12, 0)),
        )
        self.assertEqual(conflicts, [])

    def test_completed_matches_do_not_conflict(self):
        from datetime import datetime
        from django.utils import timezone

        Match.objects.create(
            event=self.event,
            scheduled_start=timezone.make_aware(datetime(2026, 3, 2, 8, 0)),
            scheduled_end=timezone.make_aware(datetime(2026, 3, 2, 10, 0)),
            venue=self.venue,
            status=Match.Status.COMPLETED,
        )
        conflicts = find_venue_conflicts(
            self.venue,
            timezone.make_aware(datetime(2026, 3, 2, 9, 0)),
            timezone.make_aware(datetime(2026, 3, 2, 11, 0)),
        )
        self.assertEqual(conflicts, [])


class SeedSportsCommandTest(TestCase):
    """The seeded sports meet must be complete, consistent, and conflict free."""

    @classmethod
    def setUpTestData(cls):
        call_command('seed_sports', quiet=True)
        cls.competition = Competition.objects.get(name='JHCSC INTRAMURAL SPORTS MEET 2026')

    def test_creates_reference_data(self):
        self.assertGreaterEqual(SportType.objects.count(), 8)
        self.assertGreaterEqual(Venue.objects.count(), 8)
        self.assertEqual(Team.objects.filter(status=Team.Status.APPROVED).count(), 12)
        self.assertEqual(TeamMembership.objects.count(), 60)
        self.assertEqual(TeamStaff.objects.filter(role=TeamStaff.Role.COACH).count(), 12)

    def test_creates_events_across_formats(self):
        formats = set(SportsEvent.objects.values_list('format', flat=True))
        self.assertIn(SportsEvent.Format.SINGLE_ELIMINATION, formats)
        self.assertIn(SportsEvent.Format.ROUND_ROBIN, formats)
        self.assertIn(SportsEvent.Format.GROUP_STAGE, formats)
        self.assertIn(SportsEvent.Format.DOUBLE_ELIMINATION, formats)

    def test_every_match_is_scheduled_with_a_venue(self):
        for match in Match.objects.all():
            self.assertIsNotNone(match.scheduled_start, f'{match} has no start time')
            self.assertIsNotNone(match.scheduled_end, f'{match} has no end time')
            self.assertIsNotNone(match.venue_id, f'{match} has no venue')
            self.assertGreater(match.scheduled_end, match.scheduled_start)

    def test_no_venue_is_double_booked(self):
        bookings = defaultdict(list)
        for match in Match.objects.exclude(venue__isnull=True):
            bookings[match.venue_id].append(match)

        for venue_id, matches in bookings.items():
            matches.sort(key=lambda m: m.scheduled_start)
            for index, first in enumerate(matches):
                for second in matches[index + 1:]:
                    if second.scheduled_start >= first.scheduled_end:
                        break
                    self.assertGreaterEqual(
                        first.scheduled_end, second.scheduled_start,
                        f'Venue {venue_id} double booked by {first} and {second}',
                    )

    def test_matches_stay_within_playing_hours(self):
        for match in Match.objects.all():
            self.assertGreaterEqual(match.scheduled_start.hour, 8, f'{match} starts too early')
            self.assertLessEqual(match.scheduled_end.hour, 18, f'{match} ends too late')

    def test_elapsed_matches_have_results(self):
        now = timezone.now()
        elapsed = Match.objects.filter(scheduled_start__lt=now)
        self.assertTrue(elapsed.exists())
        for match in elapsed:
            self.assertEqual(match.status, Match.Status.COMPLETED, f'{match} elapsed unplayed')
            entries = match.entries.all()
            self.assertEqual(entries.count(), 2)
            for entry in entries:
                self.assertIsNotNone(entry.score, f'{match} has an unscored entry')
            self.assertTrue(any(e.is_winner for e in entries), f'{match} has no winner')

    def test_future_matches_are_awaiting_entrants(self):
        now = timezone.now()
        future = Match.objects.filter(scheduled_start__gte=now)
        self.assertTrue(future.exists())
        self.assertEqual(
            set(future.values_list('status', flat=True)),
            {Match.Status.SCHEDULED},
        )

    def test_group_stage_produces_a_knockout(self):
        event = SportsEvent.objects.get(
            name='Volleyball - Men', competition=self.competition,
        )
        self.assertTrue(event.matches.filter(group__isnull=False).exists())
        self.assertTrue(event.matches.filter(round_number__gt=1).exists())
        standings = compute_group_stage_standings(event)
        self.assertIsNotNone(standings['knockout'])
        self.assertEqual(
            len([r for g in standings['groups'] for r in g['rows'] if r['qualifies']]),
            4,
        )

    def test_elimination_events_declare_a_champion(self):
        for name in ('Basketball - Men', 'Sepak Takraw - Open'):
            event = SportsEvent.objects.get(name=name, competition=self.competition)
            standings = compute_standings(event)
            champions = [row for row in standings if row['is_champion']]
            self.assertEqual(len(champions), 1, f'{name} has {len(champions)} champions')
            self.assertEqual(standings[0]['rank'], 1)

    def test_individual_events_use_seeded_athletes(self):
        """Individual entries must not pull in unrelated participants."""
        seeded = {
            p.id for p in Participant.objects.filter(
                email__startswith='athlete.sport'
            )
        }
        for name in ('Chess - Open Division', 'Badminton - Women Singles'):
            event = SportsEvent.objects.get(name=name, competition=self.competition)
            ids = set(event.entries.values_list('participant_id', flat=True))
            self.assertTrue(ids)
            self.assertTrue(
                ids.issubset(seeded),
                f'{name} referenced participants outside the sports roster',
            )

    def test_gendered_events_match_their_division(self):
        event = SportsEvent.objects.get(
            name='Badminton - Women Singles', competition=self.competition,
        )
        genders = set(
            event.entries.values_list('participant__gender', flat=True)
        )
        self.assertEqual(genders, {'female'})

    def test_team_events_reference_approved_teams(self):
        team_events = SportsEvent.objects.exclude(team_based=False)
        for event in team_events:
            for team_id in event.entries.values_list('team_id', flat=True):
                self.assertEqual(Team.objects.get(id=team_id).status, Team.Status.APPROVED)

    def test_is_idempotent(self):
        before = {
            'sports': SportType.objects.count(),
            'venues': Venue.objects.count(),
            'teams': Team.objects.count(),
            'events': SportsEvent.objects.count(),
            'matches': Match.objects.count(),
        }
        call_command('seed_sports', quiet=True)
        after = {
            'sports': SportType.objects.count(),
            'venues': Venue.objects.count(),
            'teams': Team.objects.count(),
            'events': SportsEvent.objects.count(),
            'matches': Match.objects.count(),
        }
        self.assertEqual(before, after)

    def test_flush_removes_previous_sports_data(self):
        call_command('seed_sports', flush=True, quiet=True)
        self.assertTrue(Match.objects.exists())
        self.assertEqual(
            SportsEvent.objects.count(),
            len(EVENT_SPECS),
        )

    def test_targets_an_existing_competition(self):
        call_command('seed_sports', competition=str(self.competition.id), quiet=True)
        self.assertEqual(
            self.competition.sport_events.count(),
            len(EVENT_SPECS),
        )


class SportsNavigationPagesTest(TestCase):
    """The hub and match board are the admin's entry points into sports data."""

    @classmethod
    def setUpTestData(cls):
        call_command('seed_sports', quiet=True)
        cls.admin = User.objects.get(username='admin')
        cls.competition = Competition.objects.get(name='JHCSC INTRAMURAL SPORTS MEET 2026')

    def setUp(self):
        self.client.force_login(self.admin)

    def test_hub_lists_competitions_and_events(self):
        response = self.client.get(reverse('sports_hub'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.competition.name)
        self.assertContains(response, 'Basketball - Men')
        self.assertContains(response, 'Badminton - Women Singles')
        self.assertEqual(
            len(response.context['competition_rows']), 1,
        )
        self.assertEqual(response.context['stats']['matches'], Match.objects.count())

    def test_hub_offers_event_management_for_every_competition(self):
        from competitions.models import Competition
        fresh = Competition.objects.create(
            name='Fresh Meet',
            start_date='2026-06-01',
            end_date='2026-06-02',
            created_by=self.admin,
        )
        event = SportsEvent.objects.first()
        response = self.client.get(reverse('sports_hub'))
        self.assertEqual(response.status_code, 200)
        # Competitions with zero events are listed too.
        self.assertContains(response, fresh.name)
        self.assertContains(response, reverse('create_sport_event', args=[fresh.id]))
        # Existing events expose direct management links.
        self.assertContains(response, reverse('create_sport_event', args=[self.competition.id]))
        self.assertContains(response, reverse('edit_sport_event', args=[event.id]))
        self.assertContains(response, 'Manage events')
        self.assertContains(response, 'Add sport event')

    def test_hub_events_stat_card(self):
        response = self.client.get(reverse('sports_hub'))
        self.assertEqual(response.context['stats']['events'], SportsEvent.objects.count())
        # Card + header button both surface the events section.
        self.assertContains(response, '>Sport events</p>')
        self.assertContains(response, 'href="#sport-events"')
        self.assertEqual(response.context['stats']['events_open'] + response.context['stats']['events_done'], response.context['stats']['events'] - SportsEvent.objects.filter(status='CANCELLED').count())

    def test_hub_flags_overdue_matches(self):
        response = self.client.get(reverse('sports_hub'))
        overdue = response.context['overdue']
        now = timezone.now()
        for match in overdue:
            self.assertLess(match.scheduled_start, now)
            self.assertEqual(match.status, Match.Status.SCHEDULED)

    def test_board_groups_matches_by_day(self):
        response = self.client.get(reverse('match_board'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['total'], Match.objects.count())
        self.assertGreater(len(response.context['days']), 1)
        day_count = sum(len(matches) for matches in response.context['days'].values())
        self.assertEqual(day_count + len(response.context['unscheduled']),
                         Match.objects.count())

    def test_board_filters_by_status(self):
        response = self.client.get(reverse('match_board'), {'status': 'COMPLETED'})
        shown = [
            match for matches in response.context['days'].values() for match in matches
        ]
        self.assertEqual(
            response.context['total'],
            Match.objects.filter(status=Match.Status.COMPLETED).count(),
        )
        for match in shown:
            self.assertEqual(match.status, Match.Status.COMPLETED)

    def test_board_filters_by_competition(self):
        response = self.client.get(
            reverse('match_board'), {'competition': self.competition.id},
        )
        self.assertEqual(
            response.context['total'],
            Match.objects.filter(event__competition=self.competition).count(),
        )

    def test_board_ignores_a_malformed_day(self):
        response = self.client.get(reverse('match_board'), {'day': 'not-a-date'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['filter_state']['day'], '')

    def test_board_day_filter_narrows_to_one_day(self):
        first = Match.objects.exclude(scheduled_start__isnull=True).order_by(
            'scheduled_start').first()
        day_value = timezone.localtime(first.scheduled_start).strftime('%Y-%m-%d')
        response = self.client.get(reverse('match_board'), {'day': day_value})
        # Only the chosen day is rendered, but the tabs still span every day.
        self.assertEqual(len(response.context['days']), 1)
        self.assertGreater(len(response.context['day_keys']), 1)
        # The selected day drives the previous/next navigation.
        self.assertEqual(response.context['selected_index'], 0)
        self.assertIsNone(response.context['prev_day'])
        self.assertIsNotNone(response.context['next_day'])

    def test_board_day_navigation_respects_the_ends(self):
        """The first and last day must not wrap around to the opposite end."""
        days = list(self._board_day_keys())
        self.assertGreater(len(days), 2)

        first = days[0]
        context = self.client.get(
            reverse('match_board'),
            {'day': first.strftime('%Y-%m-%d')},
        ).context
        self.assertIsNone(context['prev_day'], 'first day offered a previous day')
        self.assertIsNotNone(context['next_day'])

        last = days[-1]
        context = self.client.get(
            reverse('match_board'),
            {'day': last.strftime('%Y-%m-%d')},
        ).context
        self.assertIsNotNone(context['prev_day'])
        self.assertIsNone(context['next_day'], 'last day offered a next day')

    def _board_day_keys(self):
        response = self.client.get(reverse('match_board'))
        return response.context['day_keys']

    def test_board_offers_day_navigation(self):
        response = self.client.get(reverse('match_board'))
        self.assertEqual(response.context['selected_index'], None)
        self.assertIsNone(response.context['prev_day'])
        self.assertIsNone(response.context['next_day'])
        self.assertGreater(len(response.context['day_keys']), 1)

    def test_navigation_pages_require_management_role(self):
        spectator = User.objects.create_user('nav_spectator', 'nav@test.com', 'pass')
        profile, _ = UserProfile.objects.get_or_create(user=spectator)
        profile.role = UserProfile.Role.SPECTATOR
        profile.save()

        self.client.force_login(spectator)
        for url in (reverse('sports_hub'), reverse('match_board')):
            self.assertEqual(self.client.get(url).status_code, 403)

    def test_sidebar_and_pages_link_back_to_the_hub(self):
        hub = self.client.get(reverse('sports_hub'))
        self.assertContains(hub, reverse('match_board'))

        for url in (reverse('sport_type_list'), reverse('venue_list')):
            self.assertContains(self.client.get(url), reverse('sports_hub'))

        event = self.competition.sport_events.first()
        self.assertContains(
            self.client.get(reverse('competition_detail', args=[self.competition.id])),
            reverse('competition_sport_events', args=[self.competition.id]),
        )
        self.assertContains(
            self.client.get(reverse('match_schedule', args=[event.id])),
            reverse('match_board'),
        )