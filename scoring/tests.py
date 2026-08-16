from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from competitions.models import Competition, Round, Criterion
from participants.models import Participant, ParticipantCompetition
from judges.models import Judge, JudgeAssignment
from .models import Score, CompetitionResult
from .services import calculate_participant_total_score, calculate_rankings


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
