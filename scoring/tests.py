from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from competitions.models import Competition, Round, Criterion
from participants.models import Participant, ParticipantCompetition
from judges.models import Judge, JudgeAssignment
from accounts.models import UserProfile
from teams.models import Team
from .models import Score, CompetitionResult, Award, AwardRecipient, ScoreChangeLog
from .services import (
    calculate_participant_total_score,
    calculate_rankings,
    compute_medal_tally,
    compute_overall_medal_tally,
    contestant_identity,
    medal_points_for,
)
from sports.models import Match, SportsEvent, SportType, Venue
from sports.services import event_podium, generate_bracket, record_match_result


class BaseScoringTest(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser('admin', 'a@a.com', 'pass')
        self.competition = Competition.objects.create(
            name='Test Comp', description='d', status='ACTIVE',
            start_date='2026-01-01 00:00:00', end_date='2026-01-02 00:00:00',
            created_by=self.admin,
        )
        self.round = Round.objects.create(
            competition=self.competition, name='Round 1', description='d',
            order=1, status='ONGOING', weight_percentage=Decimal('100'),
        )
        self.criterion = Criterion.objects.create(
            round=self.round, name='C1', description='d', max_score=Decimal('100'),
        )
        self.participant = Participant.objects.create(
            name='P1', email='p1@a.com', phone='123', age=20, status='ACTIVE',
        )
        self.judge_user = User.objects.create_user('judge', 'j@a.com', 'pass')
        self.judge = Judge.objects.create(user=self.judge_user, phone='123', status='ACTIVE')
        self.assignment = JudgeAssignment.objects.create(
            judge=self.judge, competition=self.competition, status='ACTIVE',
        )
        self.assignment.rounds.add(self.round)


class CalculateTotalScoreTest(BaseScoringTest):
    def test_averages_submitted_scores_across_judges(self):
        judge2 = Judge.objects.create(
            user=User.objects.create_user('judge2', 'j2@a.com', 'pass'),
            phone='456', status='ACTIVE',
        )
        Score.objects.create(participant=self.participant, criterion=self.criterion,
                             judge=self.judge, score=Decimal('80'), status='SUBMITTED')
        Score.objects.create(participant=self.participant, criterion=self.criterion,
                             judge=judge2, score=Decimal('100'), status='SUBMITTED')

        total = calculate_participant_total_score(self.participant, self.round, include_draft=False)
        # The judge average for this criterion is 90 points.
        self.assertEqual(total, Decimal('90.00'))

    def test_sums_criterion_points_without_scaling_them_twice(self):
        self.criterion.max_score = Decimal('40')
        self.criterion.save(update_fields=['max_score'])
        second_criterion = Criterion.objects.create(
            round=self.round,
            name='C2',
            description='d',
            max_score=Decimal('60'),
        )
        Score.objects.create(
            participant=self.participant,
            criterion=self.criterion,
            judge=self.judge,
            score=Decimal('30'),
            status='SUBMITTED',
        )
        Score.objects.create(
            participant=self.participant,
            criterion=second_criterion,
            judge=self.judge,
            score=Decimal('50'),
            status='SUBMITTED',
        )

        total = calculate_participant_total_score(
            self.participant,
            self.round,
            include_draft=False,
        )

        self.assertEqual(total, Decimal('80.00'))

    def test_ignores_draft_scores_when_not_include_draft(self):
        Score.objects.create(participant=self.participant, criterion=self.criterion,
                             judge=self.judge, score=Decimal('50'), status='DRAFT')
        total = calculate_participant_total_score(self.participant, self.round, include_draft=False)
        self.assertEqual(total, Decimal('0.00'))


class CalculateRankingsTest(BaseScoringTest):
    def test_assigns_ranks_by_total_score(self):
        p2 = Participant.objects.create(name='P2', email='p2@a.com', phone='2', age=20, status='ACTIVE')
        Score.objects.create(participant=self.participant, criterion=self.criterion,
                             judge=self.judge, score=Decimal('80'), status='SUBMITTED')
        Score.objects.create(participant=p2, criterion=self.criterion,
                             judge=self.judge, score=Decimal('90'), status='SUBMITTED')

        calculate_rankings(self.round)

        top = CompetitionResult.objects.get(round=self.round, participant=p2)
        bottom = CompetitionResult.objects.get(round=self.round, participant=self.participant)
        self.assertEqual(top.rank, 1)
        self.assertEqual(bottom.rank, 2)


class ScoringPanelViewTest(BaseScoringTest):
    def test_requires_login(self):
        resp = self.client.get(reverse('scoring_panel', args=[self.round.id]))
        self.assertEqual(resp.status_code, 302)

    def test_unassigned_judge_is_redirected(self):
        other = User.objects.create_user('other', 'o@a.com', 'pass')
        Judge.objects.create(user=other, phone='7', status='ACTIVE')
        self.client.login(username='other', password='pass')
        resp = self.client.get(reverse('scoring_panel', args=[self.round.id]))
        self.assertRedirects(resp, reverse('judge_dashboard'))

    def test_assigned_judge_can_submit_scores(self):
        ParticipantCompetition.objects.create(
            participant=self.participant,
            competition=self.competition,
            number=1,
        )
        self.client.login(username='judge', password='pass')
        resp = self.client.post(
            reverse('scoring_panel', args=[self.round.id]),
            {'participant_id': self.participant.id,
             f'score_{self.participant.id}_{self.criterion.id}': '85'},
        )
        self.assertRedirects(resp, reverse('scoring_panel', args=[self.round.id]))
        self.assertTrue(Score.objects.filter(
            participant=self.participant, criterion=self.criterion,
            judge=self.judge, score=Decimal('85'), status='SUBMITTED',
        ).exists())

    def test_submitted_score_total_is_shown_on_the_scoring_panel(self):
        ParticipantCompetition.objects.create(
            participant=self.participant,
            competition=self.competition,
            number=1,
        )
        self.client.login(username='judge', password='pass')

        response = self.client.post(
            reverse('scoring_panel', args=[self.round.id]),
            {
                'participant_id': self.participant.id,
                f'score_{self.participant.id}_{self.criterion.id}': '85',
            },
            follow=True,
        )

        self.assertEqual(
            response.context['total_scores'][self.participant.id],
            Decimal('85.00'),
        )
        self.assertEqual(response.context['participants'][0].number, 1)

    def test_numeric_score_input_saves_a_draft_and_returns_its_total(self):
        ParticipantCompetition.objects.create(
            participant=self.participant,
            competition=self.competition,
            number=1,
        )
        self.client.login(username='judge', password='pass')

        response = self.client.post(
            reverse('update_score', args=[self.round.id]),
            {f'score_input_{self.participant.id}_{self.criterion.id}': '75'},
            headers={'HX-Request': 'true'},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b'75.0')
        self.assertTrue(Score.objects.filter(
            participant=self.participant,
            criterion=self.criterion,
            judge=self.judge,
            score=Decimal('75'),
            status='DRAFT',
        ).exists())

    def test_update_score_rejects_a_value_above_the_criterion_maximum(self):
        ParticipantCompetition.objects.create(
            participant=self.participant,
            competition=self.competition,
            number=1,
        )
        self.client.login(username='judge', password='pass')

        response = self.client.post(
            reverse('update_score', args=[self.round.id]),
            {f'score_{self.participant.id}_{self.criterion.id}': '101'},
            headers={'HX-Request': 'true'},
        )

        self.assertEqual(response.status_code, 400)
        self.assertFalse(Score.objects.filter(
            participant=self.participant,
            criterion=self.criterion,
            judge=self.judge,
        ).exists())

    def test_update_score_requires_an_active_round_assignment(self):
        ParticipantCompetition.objects.create(
            participant=self.participant,
            competition=self.competition,
            number=1,
        )
        self.assignment.status = 'INACTIVE'
        self.assignment.save(update_fields=['status'])
        self.client.login(username='judge', password='pass')

        response = self.client.post(
            reverse('update_score', args=[self.round.id]),
            {f'score_{self.participant.id}_{self.criterion.id}': '75'},
            headers={'HX-Request': 'true'},
        )

        self.assertEqual(response.status_code, 403)
        self.assertFalse(Score.objects.filter(judge=self.judge).exists())

    def test_submitted_score_cannot_be_changed_by_draft_update(self):
        ParticipantCompetition.objects.create(
            participant=self.participant,
            competition=self.competition,
            number=1,
        )
        Score.objects.create(
            participant=self.participant,
            criterion=self.criterion,
            judge=self.judge,
            score=Decimal('85'),
            status='SUBMITTED',
        )
        self.client.login(username='judge', password='pass')

        response = self.client.post(
            reverse('update_score', args=[self.round.id]),
            {f'score_{self.participant.id}_{self.criterion.id}': '25'},
            headers={'HX-Request': 'true'},
        )

        self.assertEqual(response.status_code, 409)
        saved_score = Score.objects.get(
            participant=self.participant,
            criterion=self.criterion,
            judge=self.judge,
        )
        self.assertEqual(saved_score.score, Decimal('85'))
        self.assertEqual(saved_score.status, 'SUBMITTED')


class ResultsPrintSelectionViewTest(BaseScoringTest):
    def setUp(self):
        super().setUp()
        ParticipantCompetition.objects.create(
            participant=self.participant,
            competition=self.competition,
            number=1,
        )
        self.second_round = Round.objects.create(
            competition=self.competition,
            name='Semifinal Round',
            description='Second round',
            order=2,
            status='COMPLETED',
            weight_percentage=Decimal('50'),
        )
        self.client.login(username='admin', password='pass')

    def test_results_page_print_link_tracks_the_selected_tab(self):
        response = self.client.get(
            reverse('competition_results_detail', args=[self.competition.id])
        )

        self.assertContains(response, 'data-print-view="overall"')
        self.assertContains(response, f'data-print-view="round-{self.round.id}"')
        self.assertContains(
            response,
            f'{reverse("results_print", args=[self.competition.id])}?view=overall',
        )

    def test_overall_print_preview_only_renders_overall_results(self):
        response = self.client.get(
            reverse('results_print', args=[self.competition.id]),
            {'view': 'overall'},
        )

        self.assertContains(response, 'data-print-section="overall"')
        self.assertNotContains(response, 'data-print-section="round"')
        self.assertContains(response, 'Overall results selected')

    def test_round_print_preview_only_renders_the_selected_round(self):
        response = self.client.get(
            reverse('results_print', args=[self.competition.id]),
            {'view': f'round-{self.second_round.id}'},
        )

        self.assertContains(response, 'data-print-section="round"')
        self.assertContains(response, 'Round 2: Semifinal Round')
        self.assertContains(response, 'Semifinal Round selected')
        self.assertNotContains(response, 'data-print-section="overall"')
        self.assertNotContains(response, 'Round 1: Round 1')


class ResultsAccessControlTest(BaseScoringTest):
    def setUp(self):
        super().setUp()
        self.viewer = User.objects.create_user('viewer', 'viewer@example.com', 'pass')

    def test_spectator_cannot_view_unpublished_results(self):
        self.client.force_login(self.viewer)
        response = self.client.get(
            reverse('competition_results_detail', args=[self.competition.id]),
        )
        self.assertEqual(response.status_code, 403)

    def test_spectator_can_view_published_results(self):
        self.competition.show_results = True
        self.competition.save(update_fields=['show_results'])
        self.client.force_login(self.viewer)
        response = self.client.get(
            reverse('competition_results_detail', args=[self.competition.id]),
        )
        self.assertEqual(response.status_code, 200)

    def test_management_role_can_publish_results(self):
        organizer = User.objects.create_user('organizer', 'organizer@example.com', 'pass')
        organizer.account_profile.role = UserProfile.Role.EVENT_ORGANIZER
        organizer.account_profile.save(update_fields=['role', 'updated_at'])
        self.client.force_login(organizer)

        response = self.client.post(
            reverse('toggle_results_visibility', args=[self.competition.id]),
            {'show_results': 'true'},
        )

        self.assertEqual(response.status_code, 200)
        self.competition.refresh_from_db()
        self.assertTrue(self.competition.show_results)

    def test_spectator_cannot_publish_results(self):
        self.client.force_login(self.viewer)
        response = self.client.post(
            reverse('toggle_results_visibility', args=[self.competition.id]),
            {'show_results': 'true'},
        )
        self.assertEqual(response.status_code, 403)


class AwardTest(BaseScoringTest):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.admin)

    def test_management_can_create_an_award(self):
        resp = self.client.post(reverse('create_award', args=[self.competition.id]), {
            'name': 'Most Valuable Player',
            'type': Award.Type.MVP,
            'rank': '1',
        })
        self.assertRedirects(resp, reverse('award_list', args=[self.competition.id]))
        self.assertTrue(Award.objects.filter(
            competition=self.competition, name='Most Valuable Player',
        ).exists())

    def test_award_requires_management(self):
        self.client.force_login(self.judge_user)
        self.assertEqual(self.client.get(reverse('award_list', args=[self.competition.id])).status_code, 403)

    def test_add_and_remove_recipient(self):
        award = Award.objects.create(
            competition=self.competition,
            name='Gold Medal',
            type=Award.Type.GOLD_MEDAL,
        )
        resp = self.client.post(reverse('award_recipient_add', args=[award.id]), {
            'recipient_type': AwardRecipient.RecipientType.PARTICIPANT,
            'participant': self.participant.id,
            'citation': 'Excellent performance',
        })
        self.assertRedirects(resp, reverse('award_list', args=[self.competition.id]))
        recipient = AwardRecipient.objects.get(award=award, participant=self.participant)
        self.assertEqual(recipient.citation, 'Excellent performance')

        self.client.post(reverse('award_recipient_remove', args=[recipient.id]))
        self.assertFalse(AwardRecipient.objects.filter(id=recipient.id).exists())

    def test_team_recipient_can_receive_an_award(self):
        team = Team.objects.create(
            name='Bulldogs',
            category=Team.Category.SPORTS,
            status=Team.Status.APPROVED,
            created_by=self.admin,
        )
        award = Award.objects.create(
            competition=self.competition,
            name='Best Delegation',
            type=Award.Type.TROPHY,
        )
        self.client.post(reverse('award_recipient_add', args=[award.id]), {
            'recipient_type': AwardRecipient.RecipientType.TEAM,
            'team': team.id,
        })
        self.assertTrue(AwardRecipient.objects.filter(award=award, team=team).exists())

    def test_certificate_pdf_generates_for_recipient(self):
        award = Award.objects.create(
            competition=self.competition,
            name='Certificate of Participation',
            type=Award.Type.CERTIFICATE,
        )
        recipient = AwardRecipient.objects.create(
            award=award,
            recipient_type=AwardRecipient.RecipientType.PARTICIPANT,
            participant=self.participant,
        )
        resp = self.client.get(reverse('certificate_pdf', args=[recipient.id]))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp['Content-Type'], 'application/pdf')

    def test_unrelated_user_cannot_download_certificate(self):
        award = Award.objects.create(
            competition=self.competition,
            name='Certificate',
            type=Award.Type.CERTIFICATE,
        )
        recipient = AwardRecipient.objects.create(
            award=award,
            recipient_type=AwardRecipient.RecipientType.PARTICIPANT,
            participant=self.participant,
        )
        viewer = User.objects.create_user('viewer2', 'viewer2@example.com', 'pass')
        self.client.force_login(viewer)
        self.assertEqual(self.client.get(reverse('certificate_pdf', args=[recipient.id])).status_code, 403)


class MedalTallyTest(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser('admin', 'a@a.com', 'pass')
        self.competition = Competition.objects.create(
            name='Test Comp', description='d', status='ACTIVE',
            start_date='2026-01-01 00:00:00', end_date='2026-01-02 00:00:00',
            created_by=self.admin,
        )
        self.team_a = Team.objects.create(name='Team A', category=Team.Category.SPORTS, created_by=self.admin)
        self.team_b = Team.objects.create(name='Team B', category=Team.Category.SPORTS, created_by=self.admin)

    def _award(self, name, award_type, rank=None):
        return Award.objects.create(
            competition=self.competition,
            name=name,
            type=award_type,
            rank=rank,
        )

    def test_tally_sums_medal_points(self):
        gold = self._award('Gold', Award.Type.GOLD_MEDAL)
        silver = self._award('Silver', Award.Type.SILVER_MEDAL)
        bronze = self._award('Bronze', Award.Type.BRONZE_MEDAL)
        AwardRecipient.objects.create(award=gold, recipient_type=AwardRecipient.RecipientType.TEAM, team=self.team_a)
        AwardRecipient.objects.create(award=silver, recipient_type=AwardRecipient.RecipientType.TEAM, team=self.team_a)
        AwardRecipient.objects.create(award=bronze, recipient_type=AwardRecipient.RecipientType.TEAM, team=self.team_a)

        tally = compute_medal_tally(self.competition)
        self.assertEqual(len(tally['rows']), 1)
        row = tally['rows'][0]
        self.assertEqual(row['name'], 'Team A')
        self.assertEqual(row['gold'], 1)
        self.assertEqual(row['silver'], 1)
        self.assertEqual(row['bronze'], 1)
        self.assertEqual(row['points'], Decimal('18'))

    def test_champion_ranked_by_points(self):
        gold_a = self._award('Gold A', Award.Type.GOLD_MEDAL)
        silver_b = self._award('Silver B', Award.Type.SILVER_MEDAL)
        AwardRecipient.objects.create(award=gold_a, recipient_type=AwardRecipient.RecipientType.TEAM, team=self.team_a)
        AwardRecipient.objects.create(award=silver_b, recipient_type=AwardRecipient.RecipientType.TEAM, team=self.team_b)

        tally = compute_medal_tally(self.competition)
        self.assertEqual(tally['champion']['name'], 'Team A')
        self.assertEqual(tally['rows'][0]['rank'], 1)
        self.assertEqual(tally['rows'][1]['rank'], 2)

    def test_non_medal_awards_ignored(self):
        trophy = self._award('Trophy', Award.Type.TROPHY)
        AwardRecipient.objects.create(award=trophy, recipient_type=AwardRecipient.RecipientType.TEAM, team=self.team_a)
        tally = compute_medal_tally(self.competition)
        self.assertEqual(tally['rows'], [])

    def test_inactive_awards_excluded(self):
        gold = self._award('Gold', Award.Type.GOLD_MEDAL)
        gold.is_active = False
        gold.save(update_fields=['is_active'])
        AwardRecipient.objects.create(award=gold, recipient_type=AwardRecipient.RecipientType.TEAM, team=self.team_a)
        tally = compute_medal_tally(self.competition)
        self.assertEqual(tally['rows'], [])

    def test_medal_tally_page_renders(self):
        gold = self._award('Gold', Award.Type.GOLD_MEDAL)
        AwardRecipient.objects.create(award=gold, recipient_type=AwardRecipient.RecipientType.TEAM, team=self.team_a)
        self.client.force_login(self.admin)
        response = self.client.get(reverse('medal_tally', args=[self.competition.id]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Team A')
        self.assertContains(response, '10')

    def test_scoreboard_page_renders(self):
        from sports.models import Match, MatchEntry, SportsEvent, SportType
        sport = SportType.objects.create(name='Basketball', team_based=True)
        event = SportsEvent.objects.create(
            competition=self.competition,
            sport_type=sport,
            name='Basketball',
            team_based=True,
            format=SportsEvent.Format.ROUND_ROBIN,
        )
        match = Match.objects.create(event=event, name='Match 1', status=Match.Status.ONGOING)
        MatchEntry.objects.create(match=match, team=self.team_a, side=1, score=Decimal('10'))
        MatchEntry.objects.create(match=match, team=self.team_b, side=2, score=Decimal('8'))
        self.client.force_login(self.admin)
        response = self.client.get(reverse('scoreboard', args=[self.competition.id]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Basketball')
        self.assertContains(response, 'Team A')

    def test_scoreboard_htmx_partial(self):
        from sports.models import Match, MatchEntry, SportsEvent, SportType
        sport = SportType.objects.create(name='Basketball', team_based=True)
        event = SportsEvent.objects.create(
            competition=self.competition,
            sport_type=sport,
            name='Basketball',
            team_based=True,
            format=SportsEvent.Format.ROUND_ROBIN,
        )
        match = Match.objects.create(event=event, name='Match 1', status=Match.Status.ONGOING)
        MatchEntry.objects.create(match=match, team=self.team_a, side=1, score=Decimal('10'))
        MatchEntry.objects.create(match=match, team=self.team_b, side=2, score=Decimal('8'))
        self.client.force_login(self.admin)
        response = self.client.get(
            reverse('scoreboard', args=[self.competition.id]),
            HTTP_HX_REQUEST='true',
        )
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, '<html')


class SportPodiumTest(TestCase):
    """A finished sport event yields a podium; an unfinished one never does."""

    def setUp(self):
        self.admin = User.objects.create_superuser('admin', 'a@a.com', 'pass')
        self.competition = Competition.objects.create(
            name='Meet', description='d', status='ACTIVE',
            start_date='2026-01-01 00:00:00', end_date='2026-01-05 00:00:00',
            created_by=self.admin,
        )
        self.sport = SportType.objects.create(name='Basketball', team_based=True)
        self.event = SportsEvent.objects.create(
            competition=self.competition, sport_type=self.sport,
            name='Basketball', team_based=True,
            format=SportsEvent.Format.SINGLE_ELIMINATION,
        )
        self.teams = [
            Team.objects.create(name=f'T{i}', category=Team.Category.SPORTS, created_by=self.admin)
            for i in range(4)
        ]
        from sports.models import EventEntry
        for team in self.teams:
            EventEntry.objects.create(event=self.event, team=team, status='CONFIRMED')

    def _play_everything(self):
        generate_bracket(self.event)
        for match in self.event.matches.order_by('round_number', 'id'):
            if match.entries.count() == 2:
                record_match_result(match, {1: 10, 2: 5})

    def test_unfinished_event_has_no_podium(self):
        generate_bracket(self.event)
        self.assertEqual(event_podium(self.event), [])

    def test_finished_event_yields_gold_silver_bronze(self):
        self._play_everything()
        podium = event_podium(self.event)
        self.assertEqual([medal for _, medal in podium], ['gold', 'silver', 'bronze'])
        self.assertEqual(len(podium), 3)

    def test_champion_takes_gold(self):
        self._play_everything()
        gold_entry, _ = event_podium(self.event)[0]
        self.assertEqual(gold_entry.display_name, self.teams[0].name)

    def test_event_without_matches_has_no_podium(self):
        self.assertEqual(event_podium(self.event), [])

    def test_tally_counts_sports_medals(self):
        self._play_everything()
        tally = compute_medal_tally(self.competition)
        self.assertTrue(tally['rows'])
        self.assertEqual(sum(row['gold'] for row in tally['rows']), 1)
        self.assertEqual(sum(row['silver'] for row in tally['rows']), 1)
        self.assertEqual(sum(row['bronze'] for row in tally['rows']), 1)
        self.assertEqual(tally['champion']['name'], self.teams[0].name)


class OverallMedalTallyTest(TestCase):
    """Sports podiums and judged results merge into a single table."""

    def setUp(self):
        self.admin = User.objects.create_superuser('admin', 'a@a.com', 'pass')
        self.client.force_login(self.admin)
        self.sport_comp = Competition.objects.create(
            name='Sports Meet', description='d', status='COMPLETED',
            start_date='2026-01-01 00:00:00', end_date='2026-01-05 00:00:00',
            created_by=self.admin,
        )
        self.judged = Competition.objects.create(
            name='Singing', description='d', status='COMPLETED',
            start_date='2026-01-01 00:00:00', end_date='2026-01-05 00:00:00',
            created_by=self.admin,
        )

    def _add_sports_podium(self):
        sport = SportType.objects.create(name='Basketball', team_based=True)
        event = SportsEvent.objects.create(
            competition=self.sport_comp, sport_type=sport, name='Basketball',
            team_based=True, format=SportsEvent.Format.SINGLE_ELIMINATION,
        )
        teams = [
            Team.objects.create(name=f'Sports {i}', category=Team.Category.SPORTS, created_by=self.admin)
            for i in range(4)
        ]
        from sports.models import EventEntry
        for team in teams:
            EventEntry.objects.create(event=event, team=team, status='CONFIRMED')
        generate_bracket(event)
        for match in event.matches.order_by('round_number', 'id'):
            if match.entries.count() == 2:
                record_match_result(match, {1: 10, 2: 5})
        return teams[0]

    def _add_judged_podium(self):
        round_obj = Round.objects.create(
            competition=self.judged, name='Final', description='d', order=1,
            status='COMPLETED', weight_percentage=Decimal('100'),
        )
        Criterion.objects.create(round=round_obj, name='Craft', description='d', max_score=Decimal('100'))
        participants = []
        for i, score in enumerate([Decimal('90'), Decimal('80'), Decimal('70')], start=1):
            participant = Participant.objects.create(
                name=f'Judge P{i}', email=f'p{i}@t.com', phone='0917', age=20,
                gender='male', status='ACTIVE',
            )
            ParticipantCompetition.objects.create(
                participant=participant, competition=self.judged, number=i,
            )
            judge = Judge.objects.create(
                user=User.objects.create_user(f'j{i}', f'j{i}@t.com', 'pass'),
            )
            Score.objects.create(
                participant=participant, criterion=round_obj.criteria.first(),
                judge=judge, score=score, status='SUBMITTED',
            )
            participants.append(participant)
        calculate_rankings(round_obj)
        self.judged.status = 'COMPLETED'
        self.judged.save()
        return participants

    def test_sports_and_judged_medals_combine(self):
        sports_champion = self._add_sports_podium()
        self._add_judged_podium()

        tally = compute_overall_medal_tally()
        names = {row['name'] for row in tally['rows']}
        self.assertIn(sports_champion.name, names)
        self.assertIn('Judge P1', names)
        self.assertEqual(tally['totals']['sports'], 3)
        self.assertEqual(tally['totals']['standings'], 3)

    def test_breakdown_covers_every_competition(self):
        self._add_sports_podium()
        self._add_judged_podium()
        tally = compute_overall_medal_tally()
        covered = {entry['competition'].name for entry in tally['breakdown']}
        self.assertEqual(covered, {'Sports Meet', 'Singing'})

    def test_running_competition_contributes_nothing(self):
        self.judged.status = 'ACTIVE'
        self.judged.save()
        self._add_judged_podium()
        self.judged.status = 'ACTIVE'
        self.judged.save()
        tally = compute_overall_medal_tally()
        self.assertEqual(tally['totals']['standings'], 0)

    def test_manual_awards_override_standings(self):
        self._add_judged_podium()
        award = Award.objects.create(
            competition=self.judged, name='Gold', type=Award.Type.GOLD_MEDAL, is_active=True,
        )
        manual = Participant.objects.create(
            name='Manual Winner', email='mw@t.com', phone='0917', age=20,
            gender='male', status='ACTIVE',
        )
        AwardRecipient.objects.create(
            award=award, recipient_type=AwardRecipient.RecipientType.PARTICIPANT,
            participant=manual,
        )
        tally = compute_overall_medal_tally()
        names = {row['name'] for row in tally['rows']}
        self.assertIn('Manual Winner', names)
        # Standings must not add a second podium on top of the manual award.
        self.assertEqual(tally['totals']['standings'], 0)
        self.assertEqual(tally['totals']['award'], 1)

    def test_identity_groups_participant_under_active_team(self):
        from teams.models import TeamMembership
        team = Team.objects.create(name='Crew', category=Team.Category.SPORTS, created_by=self.admin)
        participant = Participant.objects.create(
            name='Member', email='m@t.com', phone='0917', age=20,
            gender='male', status='ACTIVE',
        )
        TeamMembership.objects.create(team=team, participant=participant, status='ACTIVE')
        key, name = contestant_identity(participant=participant)
        self.assertEqual(key, ('team', team.id))
        self.assertEqual(name, 'Crew')

    def test_identity_falls_back_to_delegation_then_individual(self):
        participant = Participant.objects.create(
            name='Solo', email='s@t.com', phone='0917', age=20,
            gender='male', status='ACTIVE', team_name='Grey Wolves',
        )
        key, name = contestant_identity(participant=participant)
        self.assertEqual(key, ('delegation', 'grey wolves'))
        self.assertEqual(name, 'Grey Wolves')

        participant.team_name = ''
        participant.save()
        key, name = contestant_identity(participant=participant)
        self.assertEqual(key, ('individual', participant.id))

    def test_overall_page_renders(self):
        self._add_sports_podium()
        self._add_judged_podium()
        response = self.client.get(reverse('overall_medal_tally'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Overall medal tally')
        self.assertContains(response, 'Breakdown by competition')

    def test_overall_page_empty_state(self):
        response = self.client.get(reverse('overall_medal_tally'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'No medals to tally yet')

    def test_overall_page_requires_management_role(self):
        spectator = User.objects.create_user('tally_viewer', 'v@t.com', 'pass')
        profile, _ = UserProfile.objects.get_or_create(user=spectator)
        profile.role = UserProfile.Role.SPECTATOR
        profile.save()
        self.client.force_login(spectator)
        response = self.client.get(reverse('overall_medal_tally'))
        self.assertEqual(response.status_code, 403)

    def test_per_competition_page_links_to_overall(self):
        response = self.client.get(reverse('medal_tally', args=[self.judged.id]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, reverse('overall_medal_tally'))

    def test_csv_export_includes_overall(self):
        self._add_sports_podium()
        response = self.client.get(reverse('export_medal_tally_csv'))
        self.assertEqual(response.status_code, 200)
        body = response.content.decode('utf-8-sig')
        self.assertIn('OVERALL', body)


class CriterionWeightScoringTest(BaseScoringTest):
    def test_weighted_criteria_use_percentage_sum(self):
        second = Criterion.objects.create(
            round=self.round, name='C2', description='d', max_score=Decimal('100'),
        )
        self.criterion.weight_percentage = Decimal('60')
        self.criterion.save(update_fields=['weight_percentage'])
        second.weight_percentage = Decimal('40')
        second.save(update_fields=['weight_percentage'])

        Score.objects.create(participant=self.participant, criterion=self.criterion,
                             judge=self.judge, score=Decimal('90'), status='SUBMITTED')
        Score.objects.create(participant=self.participant, criterion=second,
                             judge=self.judge, score=Decimal('80'), status='SUBMITTED')

        total = calculate_participant_total_score(self.participant, self.round, include_draft=False)
        # 90 * 60% + 80 * 40% = 86
        self.assertEqual(total, Decimal('86.00'))

    def test_zero_weights_keep_legacy_sum(self):
        Score.objects.create(participant=self.participant, criterion=self.criterion,
                             judge=self.judge, score=Decimal('90'), status='SUBMITTED')
        total = calculate_participant_total_score(self.participant, self.round, include_draft=False)
        self.assertEqual(total, Decimal('90.00'))


class VerifiedScoresCountTest(BaseScoringTest):
    def test_verified_scores_are_counted_in_totals_and_rankings(self):
        p2 = Participant.objects.create(name='P2', email='p2@a.com', phone='2', age=20, status='ACTIVE')
        Score.objects.create(participant=self.participant, criterion=self.criterion,
                             judge=self.judge, score=Decimal('80'), status='VERIFIED')
        Score.objects.create(participant=p2, criterion=self.criterion,
                             judge=self.judge, score=Decimal('90'), status='VERIFIED')

        calculate_rankings(self.round)

        top = CompetitionResult.objects.get(round=self.round, participant=p2)
        self.assertEqual(top.rank, 1)
        bottom = CompetitionResult.objects.get(round=self.round, participant=self.participant)
        self.assertEqual(bottom.total_score, Decimal('80.00'))


class ResultVerificationFlowTest(BaseScoringTest):
    def setUp(self):
        super().setUp()
        self.client.login(username='admin', password='pass')
        self.score = Score.objects.create(
            participant=self.participant, criterion=self.criterion,
            judge=self.judge, score=Decimal('85'), status='SUBMITTED',
        )

    def test_verify_flips_submitted_scores_and_logs_history(self):
        resp = self.client.post(reverse('verify_round_scores', args=[self.round.id]))
        self.assertRedirects(
            resp, reverse('round_results', args=[self.competition.id, self.round.id]),
            target_status_code=302,
        )
        self.score.refresh_from_db()
        self.assertEqual(self.score.status, 'VERIFIED')
        self.assertTrue(ScoreChangeLog.objects.filter(
            score=self.score, action=ScoreChangeLog.Action.VERIFIED,
        ).exists())

    def test_unverify_reverts_to_submitted(self):
        self.score.status = 'VERIFIED'
        self.score.save(update_fields=['status'])
        self.client.post(reverse('unverify_round_scores', args=[self.round.id]))
        self.score.refresh_from_db()
        self.assertEqual(self.score.status, 'SUBMITTED')
        self.assertTrue(ScoreChangeLog.objects.filter(
            score=self.score, action=ScoreChangeLog.Action.UNVERIFIED,
        ).exists())

    def test_verification_requires_management(self):
        self.client.logout()
        self.client.login(username='judge', password='pass')
        resp = self.client.post(reverse('verify_round_scores', args=[self.round.id]))
        self.assertEqual(resp.status_code, 403)
        self.score.refresh_from_db()
        self.assertEqual(self.score.status, 'SUBMITTED')

    def test_draft_scores_are_not_verified(self):
        self.score.status = 'DRAFT'
        self.score.save(update_fields=['status'])
        self.client.post(reverse('verify_round_scores', args=[self.round.id]))
        self.score.refresh_from_db()
        self.assertEqual(self.score.status, 'DRAFT')

    def test_score_history_page_lists_changes(self):
        from .services import record_score_change
        record_score_change(
            self.score, ScoreChangeLog.Action.SUBMITTED,
            user=self.admin, old_score=None, old_status='',
            details='test entry',
        )
        resp = self.client.get(reverse('score_history', args=[self.competition.id]))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'P1')
        self.assertContains(resp, 'test entry')

    def test_score_history_requires_management(self):
        resp = self.client.get(reverse('score_history', args=[self.competition.id]))
        self.assertEqual(resp.status_code, 200)
        self.client.logout()
        self.client.login(username='judge', password='pass')
        resp = self.client.get(reverse('score_history', args=[self.competition.id]))
        self.assertEqual(resp.status_code, 403)


class RoundResultsVerificationControlsTest(BaseScoringTest):
    def setUp(self):
        super().setUp()
        self.round.status = 'COMPLETED'
        self.round.save(update_fields=['status'])
        CompetitionResult.objects.create(
            competition=self.competition, participant=self.participant,
            round=self.round, total_score=Decimal('85'), rank=1,
        )
        Score.objects.create(participant=self.participant, criterion=self.criterion,
                             judge=self.judge, score=Decimal('85'), status='SUBMITTED')
        self.client.login(username='admin', password='pass')

    def test_management_sees_verify_button_and_counts(self):
        resp = self.client.get(reverse('round_results', args=[self.competition.id, self.round.id]))
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.context['can_manage_round'])
        self.assertEqual(resp.context['submitted_count'], 1)
        self.assertEqual(resp.context['verified_count'], 0)
        self.assertContains(resp, reverse('verify_round_scores', args=[self.round.id]))

    def test_judge_does_not_see_verify_controls(self):
        self.client.logout()
        self.client.login(username='judge', password='pass')
        resp = self.client.get(reverse('round_results', args=[self.competition.id, self.round.id]))
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(resp.context['can_manage_round'])
        self.assertNotContains(resp, reverse('verify_round_scores', args=[self.round.id]))


class MedalPointsConfigTest(BaseScoringTest):
    def test_custom_points_come_from_competition(self):
        self.competition.gold_points = Decimal('15')
        self.competition.silver_points = Decimal('8')
        self.competition.bronze_points = Decimal('4')
        self.competition.save()
        points = medal_points_for(self.competition)
        self.assertEqual(points[Award.Type.GOLD_MEDAL], Decimal('15'))
        self.assertEqual(points[Award.Type.SILVER_MEDAL], Decimal('8'))
        self.assertEqual(points[Award.Type.BRONZE_MEDAL], Decimal('4'))

    def test_defaults_when_no_competition(self):
        points = medal_points_for(None)
        self.assertEqual(points[Award.Type.GOLD_MEDAL], Decimal('10'))
        self.assertEqual(points[Award.Type.SILVER_MEDAL], Decimal('5'))
        self.assertEqual(points[Award.Type.BRONZE_MEDAL], Decimal('3'))


class ScoreboardAccessTest(BaseScoringTest):
    def test_anonymous_can_watch_active_competition(self):
        resp = self.client.get(reverse('scoreboard', args=[self.competition.id]))
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.context['visible'])

    def test_anonymous_locked_out_before_release(self):
        self.competition.status = 'PENDING'
        self.competition.save(update_fields=['status'])
        resp = self.client.get(reverse('scoreboard', args=[self.competition.id]))
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(resp.context['visible'])
        self.assertContains(resp, 'has not opened yet')

    def test_published_scoreboard_visible_even_when_pending(self):
        self.competition.status = 'PENDING'
        self.competition.show_results = True
        self.competition.save(update_fields=['status', 'show_results'])
        resp = self.client.get(reverse('scoreboard', args=[self.competition.id]))
        self.assertTrue(resp.context['visible'])

    def test_judge_can_view_hidden_scoreboard(self):
        self.competition.status = 'PENDING'
        self.competition.save(update_fields=['status'])
        self.client.login(username='judge', password='pass')
        resp = self.client.get(reverse('scoreboard', args=[self.competition.id]))
        self.assertTrue(resp.context['visible'])


class DashboardWidgetTest(BaseScoringTest):
    def setUp(self):
        super().setUp()
        self.client.login(username='admin', password='pass')
        sport_type = SportType.objects.create(name='Chess', team_based=False)
        event = SportsEvent.objects.create(
            competition=self.competition, sport_type=sport_type,
            name='Chess Singles', format=SportsEvent.Format.SINGLE_ELIMINATION,
            status=SportsEvent.Status.SCHEDULED,
        )
        self.match = Match.objects.create(
            event=event, name='Game 1', status=Match.Status.SCHEDULED,
            scheduled_start='2026-01-01 09:00:00',
        )

    def test_dashboard_renders_new_widgets(self):
        resp = self.client.get(reverse('dashboard'))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Upcoming Matches')
        self.assertContains(resp, 'Current Champions')
        self.assertContains(resp, 'Medal Standings')
        self.assertIn(self.match, list(resp.context['upcoming_matches']))


class CompetitionReportExportTest(BaseScoringTest):
    def setUp(self):
        super().setUp()
        ParticipantCompetition.objects.create(
            participant=self.participant, competition=self.competition, number=1,
        )
        Score.objects.create(participant=self.participant, criterion=self.criterion,
                             judge=self.judge, score=Decimal('85'), status='SUBMITTED')
        CompetitionResult.objects.create(
            competition=self.competition, participant=self.participant,
            round=self.round, total_score=Decimal('85'), rank=1,
        )
        self.client.login(username='admin', password='pass')

    def test_judge_score_csv(self):
        resp = self.client.get(reverse('export_judge_scores_csv', args=[self.competition.id]))
        self.assertEqual(resp.status_code, 200)
        body = resp.content.decode('utf-8-sig')
        self.assertIn('P1', body)
        self.assertIn('C1', body)
        self.assertIn('85', body)

    def test_standings_csv(self):
        resp = self.client.get(reverse('export_standings_csv', args=[self.competition.id]))
        self.assertEqual(resp.status_code, 200)
        body = resp.content.decode('utf-8-sig')
        self.assertIn('Final (weighted)', body)
        self.assertIn('P1', body)

    def test_exports_require_management(self):
        self.client.logout()
        self.client.login(username='judge', password='pass')
        resp = self.client.get(reverse('export_standings_csv', args=[self.competition.id]))
        self.assertEqual(resp.status_code, 403)
