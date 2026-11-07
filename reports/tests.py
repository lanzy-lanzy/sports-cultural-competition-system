from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import UserProfile
from competitions.models import Competition, Criterion, Round
from judges.models import Judge
from participants.models import Participant, ParticipantCompetition
from registrations.models import EventRegistration
from scoring.models import CompetitionResult, Score
from sports.models import Match, SportsEvent, SportType, Venue
from teams.models import Team, TeamMembership


class ReportsTestBase(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser('admin', 'admin@example.com', 'pass')
        self.judge_user = User.objects.create_user('judge', 'judge@example.com', 'pass')
        profile, _ = UserProfile.objects.get_or_create(user=self.judge_user)
        profile.role = UserProfile.Role.JUDGE
        profile.save()

        now = timezone.now()
        self.competition = Competition.objects.create(
            name='University Sports Meet 2026',
            description='Annual competition.',
            status='ACTIVE',
            start_date=now,
            end_date=now + timedelta(days=3),
            created_by=self.admin,
        )
        self.participant = Participant.objects.create(
            name='Maria Santos',
            email='maria.private@example.com',
            phone='09171234567',
            age=21,
            gender='female',
            status='ACTIVE',
            team_name='Team Blue',
        )
        ParticipantCompetition.objects.create(
            participant=self.participant,
            competition=self.competition,
            number=1,
        )
        self.team = Team.objects.create(
            name='Team Blue',
            category=Team.Category.SPORTS,
            status=Team.Status.APPROVED,
            created_by=self.admin,
        )
        TeamMembership.objects.create(
            team=self.team,
            participant=self.participant,
            member_number=1,
        )
        self.registration = EventRegistration.objects.create(
            registrant=self.admin,
            participant=self.participant,
            competition=self.competition,
            status=EventRegistration.Status.PENDING,
        )

        sport_type = SportType.objects.create(name='Basketball')
        self.event = SportsEvent.objects.create(
            competition=self.competition,
            sport_type=sport_type,
            name='Basketball Men',
        )
        venue = Venue.objects.create(name='Main Gymnasium')
        Match.objects.create(
            event=self.event,
            name='Opening Match',
            round_number=1,
            venue=venue,
            scheduled_start=now + timedelta(hours=2),
            scheduled_end=now + timedelta(hours=4),
        )

        self.round = Round.objects.create(
            competition=self.competition,
            name='Final Round',
            description='Final judging.',
            order=1,
            status='COMPLETED',
            weight_percentage=Decimal('100'),
        )
        self.criterion = Criterion.objects.create(
            round=self.round,
            name='Performance',
            description='Overall performance.',
            max_score=Decimal('100'),
        )
        self.judge = Judge.objects.create(
            user=self.judge_user,
            phone='09170000000',
            status='ACTIVE',
        )
        Score.objects.create(
            participant=self.participant,
            criterion=self.criterion,
            judge=self.judge,
            score=Decimal('92.50'),
            status='SUBMITTED',
        )
        CompetitionResult.objects.create(
            competition=self.competition,
            participant=self.participant,
            round=self.round,
            total_score=Decimal('92.50'),
            rank=1,
        )
        self.client.force_login(self.admin)


class ReportsHomeTests(ReportsTestBase):
    def test_reports_home_renders_official_registers(self):
        response = self.client.get(reverse('reports_home'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Reports &amp; Analytics')
        self.assertContains(response, 'Official registers')
        self.assertContains(response, 'Participant Register')
        self.assertContains(response, 'Team &amp; Delegation Rosters')
        self.assertContains(response, 'Medal Tally &amp; Standings')
        self.assertEqual(len(response.context['reports']), 5)
        self.assertEqual(response.context['stats']['participants'], 1)
        self.assertEqual(response.context['stats']['pending_registrations'], 1)

    def test_reports_home_shows_competition_documents(self):
        response = self.client.get(reverse('reports_home'))
        self.assertContains(response, 'University Sports Meet 2026')
        self.assertContains(response, reverse('export_standings_pdf', args=[self.competition.id]))
        self.assertContains(response, reverse('print_judge_scores', args=[self.competition.id]))


class ReportsPrivacyTests(ReportsTestBase):
    def test_participant_csv_omits_email(self):
        response = self.client.get(reverse('export_participants_csv'))
        self.assertEqual(response.status_code, 200)
        body = response.content.decode('utf-8-sig')
        self.assertNotIn('Email', body)
        self.assertNotIn('maria.private@example.com', body)
        self.assertIn('Maria Santos', body)

    def test_print_report_omits_email(self):
        response = self.client.get(reverse('print_participants'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Participant Register')
        self.assertNotContains(response, 'maria.private@example.com')
        self.assertNotContains(response, 'Email')

    def test_judge_score_report_omits_email(self):
        response = self.client.get(reverse('print_judge_scores', args=[self.competition.id]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Judge Score Sheet')
        self.assertContains(response, 'Maria Santos')
        self.assertNotContains(response, 'judge@example.com')


class ReportExportTests(ReportsTestBase):
    def test_pdf_exports_return_pdf_documents(self):
        endpoints = [
            reverse('export_participants_pdf'),
            reverse('export_team_rosters_pdf'),
            reverse('export_registrations_pdf'),
            reverse('export_schedule_pdf'),
            reverse('export_medal_tally_pdf'),
            reverse('export_judge_scores_pdf', args=[self.competition.id]),
            reverse('export_standings_pdf', args=[self.competition.id]),
        ]
        for url in endpoints:
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response['Content-Type'], 'application/pdf')
                self.assertTrue(response.content.startswith(b'%PDF'))
                self.assertIn('attachment;', response['Content-Disposition'])

    def test_print_views_render(self):
        endpoints = [
            (reverse('print_participants'), 'Participant Register'),
            (reverse('print_team_rosters'), 'Team &amp; Delegation Rosters'),
            (reverse('print_registrations'), 'Event Registration Register'),
            (reverse('print_schedule'), 'Official Match Schedule'),
            (reverse('print_medal_tally'), 'Medal Tally'),
            (reverse('print_judge_scores', args=[self.competition.id]), 'Judge Score Sheet'),
            (reverse('print_standings', args=[self.competition.id]), 'Competition Standings'),
        ]
        for url, expected in endpoints:
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, expected)
                self.assertContains(response, 'Print / Save as PDF')

    def test_standings_report_contains_final_and_round_sections(self):
        response = self.client.get(reverse('print_standings', args=[self.competition.id]))
        self.assertContains(response, 'Final weighted standings')
        self.assertContains(response, 'Round 1: Final Round')
        self.assertContains(response, 'Maria Santos')
        self.assertContains(response, '92.5')

    def test_medal_tally_pdf_accepts_category_filter(self):
        response = self.client.get(reverse('export_medal_tally_pdf'), {'category': 'sports'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/pdf')

    def test_exports_require_management_role(self):
        self.client.force_login(self.judge_user)
        for url in (
            reverse('export_participants_pdf'),
            reverse('print_participants'),
            reverse('export_standings_pdf', args=[self.competition.id]),
            reverse('print_judge_scores', args=[self.competition.id]),
        ):
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 403)
