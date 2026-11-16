from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from competitions.models import Competition
from scoring.services import compute_overall_medal_tally
from .models import SportsEvent, SportType, EventEntry, Match
from teams.models import Team
from .services import generate_bracket, record_match_result, compute_standings, event_podium, delete_bracket
from .workflow import proposed_podium, confirm_awards, reopen_event, resolve_ties, correct_result


class TournamentWorkflowTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_superuser('workflow-admin', 'a@example.com', None)
        cls.competition = Competition.objects.create(name='Meet', kind='SPORTS', created_by=cls.admin,
            start_date='2026-01-01T00:00:00Z', end_date='2026-02-01T00:00:00Z', status='ACTIVE')
        cls.sport = SportType.objects.create(name='Sport')

    def event(self, format, n=4, **settings):
        event = SportsEvent.objects.create(competition=self.competition, sport_type=self.sport,
            name=format, format=format, **settings)
        for i in range(n):
            team = Team.objects.create(name=f'{event.pk}-{i}', category='SPORTS', created_by=self.admin)
            EventEntry.objects.create(event=event, team=team, status='CONFIRMED')
        return event

    def finish(self, event, second_wins=False):
        for _ in range(100):
            playable = next((m for m in event.matches.exclude(status__in=['COMPLETED', 'CANCELLED']).order_by('round_number', 'id') if m.entries.count() == 2), None)
            if not playable:
                return
            # Deterministic seed order avoids artificial round-robin ties.
            entries = list(playable.entries.all())
            seed = {e.team_id: e.seed for e in event.entries.all()}
            better = min(entries, key=lambda e: seed[e.team_id])
            scores = {e.side: 10 if e.pk == better.pk else 1 for e in entries}
            if second_wins:
                scores = {1: 1, 2: 10}
            record_match_result(playable, scores)
        self.fail('Tournament failed to terminate')

    def test_six_formats_finish_and_publish_only_after_confirmation(self):
        for format in ['SINGLE_ELIMINATION', 'DOUBLE_ELIMINATION', 'ROUND_ROBIN', 'GROUP_STAGE', 'BEST_OF', 'LEAGUE']:
            with self.subTest(format=format):
                event = self.event(format, 2 if format == 'BEST_OF' else 4)
                generate_bracket(event)
                self.finish(event)
                event.refresh_from_db()
                self.assertEqual(event.status, 'REVIEW')
                self.assertEqual(event_podium(event), [])
                self.assertEqual(proposed_podium(event)[0][1], 'gold')
                confirm_awards(event, self.admin)
                event.refresh_from_db()
                self.assertEqual(event.status, 'COMPLETED')
                count = event.confirmed_awards.count()
                confirm_awards(event, self.admin)
                self.assertEqual(event.confirmed_awards.count(), count)
                self.assertGreater(len(event_podium(event)), 1)

    def test_odd_round_robin_covers_each_pair_and_double_cycle(self):
        for n in [3, 5]:
            event = self.event('ROUND_ROBIN', n, cycles=2)
            generate_bracket(event)
            self.assertEqual(event.matches.count(), n * (n - 1))
            from collections import Counter
            pairs = Counter(tuple(sorted(m.entries.values_list('team_id', flat=True))) for m in event.matches.all())
            self.assertTrue(all(count == 2 for count in pairs.values()))

    def test_byes_finish_and_shared_bronze(self):
        event = self.event('SINGLE_ELIMINATION', 5)
        generate_bracket(event)
        self.finish(event)
        self.assertEqual(proposed_podium(event)[0][0].seed, 1)
        self.assertGreaterEqual(len(proposed_podium(event)), 3)

    def test_bronze_match_generated_and_required(self):
        event = self.event('SINGLE_ELIMINATION', bronze_policy='MATCH')
        generate_bracket(event)
        self.finish(event)
        self.assertEqual(event.matches.filter(name='Bronze Match', status='COMPLETED').count(), 1)
        self.assertEqual([medal for _, medal in proposed_podium(event)], ['gold', 'silver', 'bronze'])

    def test_no_bronze_policy(self):
        event = self.event('SINGLE_ELIMINATION', bronze_policy='NONE')
        generate_bracket(event)
        self.finish(event)
        self.assertEqual(len(proposed_podium(event)), 2)

    def test_double_elimination_reset_and_two_entries(self):
        for n in [2, 3, 4, 5, 8, 9, 16]:
            event = self.event('DOUBLE_ELIMINATION', n)
            generate_bracket(event)
            self.finish(event, second_wins=True)
            self.assertTrue(event.matches.filter(name='Grand Final Reset').exists(), f'Reset missing for {n} entries')
            reset = event.matches.get(name='Grand Final Reset')
            self.assertEqual(reset.status, 'COMPLETED')
            self.assertEqual(len(proposed_podium(event)), 2 if n == 2 else 3)

    def test_best_of_clinches_and_cancels_unused_games(self):
        event = self.event('BEST_OF', 2, best_of=5)
        generate_bracket(event)
        self.finish(event)
        self.assertEqual(event.matches.filter(status='COMPLETED').count(), 3)
        self.assertEqual(event.matches.filter(status='CANCELLED').count(), 2)
        self.assertEqual(compute_standings(event)[0]['wins'], 3)

    def test_ties_block_medals_until_reasoned_resolution(self):
        event = self.event('LEAGUE', 3)
        generate_bracket(event)
        for match in event.matches.all():
            record_match_result(match, {1: 0, 2: 0})
        with self.assertRaises(ValueError):
            confirm_awards(event, self.admin)
        order = list(event.entries.values_list('pk', flat=True))
        resolve_ties(event, self.admin, order, 'Approved playoff result')
        confirm_awards(event, self.admin)
        self.assertEqual(event.confirmed_awards.count(), 3)

    def test_groups_exclude_other_groups_and_resolve_qualification_tie(self):
        event = self.event('GROUP_STAGE', 6, qualifiers_per_group=2)
        generate_bracket(event)
        for match in event.matches.all():
            record_match_result(match, {1: 0, 2: 0})
        from .services import compute_group_standings
        self.assertEqual(len(compute_group_standings(event, 'A')), 3)
        self.assertFalse(event.matches.filter(group__isnull=True).exists())
        resolve_ties(event, self.admin, list(event.entries.values_list('pk', flat=True)), 'Group playoff results')
        self.assertTrue(event.matches.filter(group__isnull=True).exists())
        self.finish(event)
        confirm_awards(event, self.admin)

    def test_reopen_withdraws_medals_and_correction_invalidates_final(self):
        event = self.event('SINGLE_ELIMINATION')
        generate_bracket(event)
        self.finish(event)
        confirm_awards(event, self.admin)
        match = event.matches.order_by('round_number', 'id').first()
        with self.assertRaises(ValueError):
            correct_result(match, self.admin, {1: 0, 2: 10}, 'Correction')
        reopen_event(event, self.admin, 'Score entry error')
        event.refresh_from_db()
        self.assertEqual(event_podium(event), [])
        correct_result(match, self.admin, {1: 0, 2: 10}, 'Corrected semifinal')
        self.assertEqual(event.matches.filter(status='COMPLETED').count(), 2)
        self.finish(event)
        confirm_awards(event, self.admin)
        self.assertEqual(event.confirmed_awards.count(), 4)

    def test_unsafe_results_and_played_bracket_deletion_blocked(self):
        event = self.event('SINGLE_ELIMINATION', 2)
        generate_bracket(event)
        match = event.matches.first()
        for scores in [{1: 1, 2: 1}, {1: 'NaN', 2: 0}, {1: 'Infinity', 2: 0}, {1: -1, 2: 0}]:
            with self.assertRaises(ValueError):
                record_match_result(match, scores)
        record_match_result(match, {1: 1, 2: 0})
        with self.assertRaises(ValueError):
            delete_bracket(event)

    def test_confirmed_team_medals_count_once_and_reopening_removes_tally(self):
        event = self.event('SINGLE_ELIMINATION', 2)
        generate_bracket(event)
        self.finish(event)
        self.assertEqual(compute_overall_medal_tally([self.competition])['totals']['gold'], 0)
        confirm_awards(event, self.admin)
        self.assertEqual(compute_overall_medal_tally([self.competition])['totals']['gold'], 1)
        reopen_event(event, self.admin, 'Review')
        self.assertEqual(compute_overall_medal_tally([self.competition])['totals']['gold'], 0)

    def test_management_pages_render_and_confirmation_requires_authorized_role(self):
        event = self.event('BEST_OF', 2)
        self.client.force_login(self.admin)
        for name in ['sport_event_detail', 'edit_sport_event', 'event_standings']:
            self.assertEqual(self.client.get(reverse(name, args=[event.pk])).status_code, 200)
        generate_bracket(event)
        self.finish(event)
        self.assertEqual(self.client.post(reverse('tournament_action', args=[event.pk]), {'action': 'confirm'}).status_code, 302)
        spectator = User.objects.create_user('spectator')
        self.client.force_login(spectator)
        self.assertEqual(self.client.post(reverse('tournament_action', args=[event.pk]), {'action': 'reopen', 'reason': 'No'}).status_code, 403)


    def test_league_playoffs_and_bronze_match_complete(self):
        event = self.event('LEAGUE', 5, playoff_count=4, bronze_policy='MATCH')
        generate_bracket(event)
        self.finish(event)
        self.assertTrue(event.matches.filter(group='League').exists())
        self.assertTrue(event.matches.filter(name='Bronze Match', status='COMPLETED').exists())
        self.assertEqual(proposed_podium(event)[0][0].seed, 1)
        self.assertEqual(sum(row['is_champion'] for row in compute_standings(event)), 1)
        confirm_awards(event, self.admin)

    def test_forfeit_is_a_recorded_win_and_loss(self):
        event = self.event('ROUND_ROBIN', 2)
        generate_bracket(event)
        match = event.matches.first()
        record_match_result(match, {}, forfeited_side=1)
        match.refresh_from_db()
        self.assertEqual(match.forfeited_side, 1)
        self.assertEqual(match.winner.side, 2)
        rows = compute_standings(event)
        self.assertEqual(rows[0]['wins'], 1)
        self.assertEqual(rows[1]['losses'], 1)

    def test_corrections_finish_again_for_every_format(self):
        for format in ['SINGLE_ELIMINATION', 'DOUBLE_ELIMINATION', 'GROUP_STAGE', 'BEST_OF', 'LEAGUE', 'ROUND_ROBIN']:
            with self.subTest(format=format):
                event = self.event(format, 2 if format == 'BEST_OF' else 4)
                generate_bracket(event)
                self.finish(event)
                match = event.matches.filter(status='COMPLETED', entries__score__isnull=False).order_by('round_number', 'pk').first()
                correct_result(match, self.admin, {1: 0, 2: 5}, 'Score correction')
                self.finish(event)
                confirm_awards(event, self.admin)
                self.assertGreater(event.confirmed_awards.count(), 1)

    def test_entries_and_rules_lock_after_generation(self):
        from .forms import SportsEventForm
        event = self.event('SINGLE_ELIMINATION')
        generate_bracket(event)
        form = SportsEventForm(instance=event)
        self.assertTrue(form.fields['format'].disabled)
        self.client.force_login(self.admin)
        entry = event.entries.first()
        self.client.post(reverse('remove_event_entry', args=[event.pk, entry.pk]))
        self.assertEqual(event.entries.count(), 4)

    def test_bronze_result_correction_does_not_change_champion(self):
        event = self.event('SINGLE_ELIMINATION', bronze_policy='MATCH')
        generate_bracket(event)
        self.finish(event)
        champion = proposed_podium(event)[0][0].pk
        bronze = event.matches.get(name='Bronze Match')
        correct_result(bronze, self.admin, {1: 0, 2: 5}, 'Bronze score corrected')
        self.assertEqual(proposed_podium(event)[0][0].pk, champion)
        self.assertEqual(sum(row['is_champion'] for row in compute_standings(event)), 1)


    def test_manual_sports_awards_do_not_duplicate_confirmed_event_medals(self):
        from scoring.models import Award, AwardRecipient
        event = self.event('SINGLE_ELIMINATION', 2)
        generate_bracket(event)
        self.finish(event)
        confirm_awards(event, self.admin)
        champion = proposed_podium(event)[0][0]
        award = Award.objects.create(competition=self.competition, name='Legacy gold', type='GOLD_MEDAL')
        AwardRecipient.objects.create(award=award, team=champion.team, recipient_type='TEAM')
        self.assertEqual(compute_overall_medal_tally([self.competition])['totals']['gold'], 1)

    def test_parent_cannot_complete_before_event_awards_are_confirmed(self):
        event = self.event('SINGLE_ELIMINATION', 2)
        self.client.force_login(self.admin)
        self.client.post(reverse('toggle_competition_status', args=[self.competition.pk]))
        self.competition.refresh_from_db()
        self.assertEqual(self.competition.status, 'ACTIVE')
        generate_bracket(event)
        self.finish(event)
        confirm_awards(event, self.admin)
        self.competition.refresh_from_db()
        self.assertEqual(self.competition.status, 'COMPLETED')

    def test_event_organizer_cannot_confirm_sports_awards(self):
        event = self.event('SINGLE_ELIMINATION', 2)
        organizer = User.objects.create_user('organizer')
        organizer.account_profile.role = 'EVENT_ORGANIZER'
        organizer.account_profile.save()
        self.client.force_login(organizer)
        self.assertEqual(self.client.post(reverse('tournament_action', args=[event.pk]), {'action': 'confirm'}).status_code, 403)

    def test_event_format_inherits_competition_default(self):
        self.competition.tournament_format = 'GROUP_KNOCKOUT'
        self.competition.save(update_fields=['tournament_format'])
        self.client.force_login(self.admin)
        response = self.client.get(reverse('create_sport_event', args=[self.competition.pk]))
        self.assertEqual(response.context['form'].initial['format'], 'GROUP_STAGE')


    def test_group_bracket_preview_is_connected_without_creating_matches(self):
        from .views import bracket_payload
        event = self.event('GROUP_STAGE', 6)
        generate_bracket(event)
        before = event.matches.count()
        payload = bracket_payload(event)
        self.assertTrue(payload['preview'])
        self.assertEqual([r['total'] for r in payload['rounds']], [2, 1])
        final_id = payload['rounds'][1]['matches'][0]['id']
        self.assertTrue(all(m['next'] == final_id for m in payload['rounds'][0]['matches']))
        self.assertTrue(all(not m['recordUrl'] for r in payload['rounds'] for m in r['matches']))
        self.assertEqual(event.matches.count(), before)
        self.client.force_login(self.admin)
        response = self.client.get(reverse('event_bracket', args=[event.pk]))
        self.assertContains(response, 'bracket-stage')
        self.assertContains(response, 'Knockout bracket preview')
        self.assertContains(response, 'Group-stage matches')
        response = self.client.get(reverse('event_bracket', args=[event.pk]), {'format': 'json'})
        self.assertTrue(response.json()['preview'])

    def test_group_knockout_uses_live_connected_matches_after_qualification(self):
        from .views import bracket_payload
        event = self.event('GROUP_STAGE', 4)
        generate_bracket(event)
        for match in list(event.matches.all()):
            record_match_result(match, {1: 10, 2: 1})
        payload = bracket_payload(event)
        self.assertFalse(payload.get('preview', False))
        self.assertEqual([r['total'] for r in payload['rounds']], [2, 1])
        final = event.matches.filter(group__isnull=True).order_by('-round_number').first()
        for match in payload['rounds'][0]['matches']:
            self.assertEqual(match['next'], final.pk)
            self.assertEqual(len(match['entries']), 2)
            self.assertTrue(match['recordUrl'])
        self.client.force_login(self.admin)
        response = self.client.get(reverse('event_bracket', args=[event.pk]))
        self.assertContains(response, 'bracket-stage')
        self.assertNotContains(response, 'Knockout bracket preview')


    def test_all_formats_have_interactive_payload_and_json_results(self):
        from .views import bracket_payload
        self.client.force_login(self.admin)
        for format, mode in [('SINGLE_ELIMINATION','elimination'), ('DOUBLE_ELIMINATION','double'), ('ROUND_ROBIN','fixtures'), ('LEAGUE','fixtures'), ('BEST_OF','series'), ('GROUP_STAGE','elimination')]:
            with self.subTest(format=format):
                event = self.event(format, 2 if format == 'BEST_OF' else 4)
                generate_bracket(event)
                payload = bracket_payload(event)
                self.assertEqual(payload.get('mode', 'elimination'), mode)
                response = self.client.get(reverse('event_bracket',args=[event.pk]), {'format':'json'})
                self.assertEqual(response.status_code,200)
                self.assertTrue(response.json()['rounds'])
                html=self.client.get(reverse('event_bracket',args=[event.pk]))
                self.assertContains(html,'bracket-search')
                self.assertContains(html,'bracket-zoom-in')
                match=next(m for m in event.matches.all() if m.status != 'COMPLETED' and m.entries.count()==2)
                result=self.client.post(reverse('record_match_result',args=[match.pk]),{'score_1':'10','score_2':'1','format':'json'})
                self.assertEqual(result.status_code,200)
                self.assertTrue(result.json()['bracket']['rounds'])
                if mode in ('fixtures','series'):
                    self.assertEqual(sum(r['wins'] for r in result.json()['bracket']['standings']),1)

    def test_double_elimination_payload_includes_loser_paths(self):
        from .views import bracket_payload
        event=self.event('DOUBLE_ELIMINATION',8)
        generate_bracket(event)
        payload=bracket_payload(event)
        all_matches=[m for r in payload['rounds'] for m in r['matches']]
        ids={m['id'] for m in all_matches}
        wb=[m for m in all_matches if m['label'].startswith('WB Round')]
        self.assertEqual(len(wb),7)
        self.assertTrue(all(m.get('loserNext') in ids for m in wb))
        self.assertTrue(any(r['label'].startswith('Losers round') for r in payload['rounds']))

    def test_league_changes_from_fixture_view_to_playoff_connections(self):
        from .views import bracket_payload
        event=self.event('LEAGUE',4,playoff_count=2)
        generate_bracket(event)
        self.assertEqual(bracket_payload(event)['mode'],'fixtures')
        self.finish(event)
        payload=bracket_payload(event)
        self.assertEqual(payload['mode'],'elimination')
        self.assertEqual(payload['rounds'][-1]['label'],'Final')
        self.assertTrue(payload['group_matches'])


    def test_live_schedule_replaces_completed_match_with_next_due_fixture(self):
        from .views import _live_event_schedule, bracket_payload
        from django.utils import timezone
        from datetime import timedelta
        event=self.event('ROUND_ROBIN',4)
        generate_bracket(event)
        matches=list(event.matches.all())
        now=timezone.now()
        for index, match in enumerate(matches[:2]):
            match.scheduled_start=now-timedelta(minutes=10-index)
            match.save(update_fields=['scheduled_start'])
        before=_live_event_schedule(event,now)
        self.assertEqual(before['current']['id'],matches[0].pk)
        record_match_result(matches[0],{1:10,2:1})
        after=_live_event_schedule(event,now)
        self.assertEqual(after['current']['id'],matches[1].pk)
        self.assertNotEqual(before['current']['id'],after['current']['id'])
        self.assertEqual(bracket_payload(event)['schedule']['current']['id'],matches[1].pk)

    def test_future_fixture_becomes_current_when_start_time_arrives(self):
        from .views import _live_event_schedule
        from django.utils import timezone
        from datetime import timedelta
        event=self.event('ROUND_ROBIN',2)
        generate_bracket(event)
        match=event.matches.first()
        now=timezone.now()
        match.scheduled_start=now+timedelta(minutes=1)
        match.save(update_fields=['scheduled_start'])
        before=_live_event_schedule(event,now)
        self.assertEqual(before['state'],'upcoming')
        self.assertIsNone(before['current'])
        self.assertEqual(before['next']['id'],match.pk)
        after=_live_event_schedule(event,now+timedelta(minutes=2))
        self.assertEqual(after['state'],'due')
        self.assertEqual(after['current']['id'],match.pk)

    def test_explicit_ongoing_match_has_priority_over_overdue_slot(self):
        from .views import _live_event_schedule
        from django.utils import timezone
        from datetime import timedelta
        event=self.event('ROUND_ROBIN',4)
        generate_bracket(event)
        first,second=list(event.matches.all())[:2]
        first.scheduled_start=timezone.now()-timedelta(hours=1)
        first.save(update_fields=['scheduled_start'])
        second.status='ONGOING'
        second.save(update_fields=['status'])
        schedule=_live_event_schedule(event)
        self.assertEqual(schedule['state'],'ongoing')
        self.assertEqual(schedule['current']['id'],second.pk)

    def test_cancelled_postponed_and_unassigned_slots_are_not_live(self):
        from .views import _live_event_schedule
        from django.utils import timezone
        event=self.event('ROUND_ROBIN',4)
        generate_bracket(event)
        event.matches.all().update(status='POSTPONED',scheduled_start=timezone.now())
        schedule=_live_event_schedule(event)
        self.assertEqual(schedule['state'],'waiting')
        self.assertIsNone(schedule['current'])
        self.assertIsNone(schedule['next'])
        event.status='CANCELLED'
        self.assertEqual(_live_event_schedule(event)['state'],'cancelled')

    def test_finished_event_has_no_stale_current_schedule(self):
        from .views import _live_event_schedule
        event=self.event('BEST_OF',2)
        generate_bracket(event)
        self.finish(event)
        schedule=_live_event_schedule(event)
        self.assertEqual(schedule['state'],'finished')
        self.assertIsNone(schedule['current'])
        self.assertIsNone(schedule['next'])

    def test_schedule_refresh_json_is_uncached_and_page_polls(self):
        event=self.event('ROUND_ROBIN',2)
        generate_bracket(event)
        self.client.force_login(self.admin)
        url=reverse('event_bracket',args=[event.pk])
        response=self.client.get(url,{'format':'json'})
        self.assertIn('no-store',response.headers['Cache-Control'])
        self.assertIn('schedule',response.json())
        html=self.client.get(url)
        self.assertContains(html,'live-schedule-content')
        self.assertContains(html,'window.setInterval(refreshSchedule,10000)')


    def test_bracket_area_follows_ongoing_event_instead_of_finished_event(self):
        from .views import _scheduled_bracket_event
        from django.utils import timezone
        from datetime import timedelta
        finished=self.event('SINGLE_ELIMINATION',2)
        generate_bracket(finished)
        self.finish(finished)
        active=self.event('ROUND_ROBIN',2)
        generate_bracket(active)
        match=active.matches.first()
        match.status='ONGOING'
        match.scheduled_start=timezone.now()-timedelta(minutes=5)
        match.save(update_fields=['status','scheduled_start'])
        self.assertEqual(_scheduled_bracket_event(finished).pk,active.pk)
        self.client.force_login(self.admin)
        url=reverse('event_bracket',args=[finished.pk])
        response=self.client.get(url,{'format':'json','follow':'1'})
        self.assertEqual(response.json()['event']['id'],active.pk)
        pinned=self.client.get(url,{'format':'json','follow':'0'})
        self.assertEqual(pinned.json()['event']['id'],finished.pk)

    def test_bracket_area_waits_for_next_event_start(self):
        from .views import _scheduled_bracket_event
        from django.utils import timezone
        from datetime import timedelta
        old=self.event('SINGLE_ELIMINATION',2)
        generate_bracket(old)
        self.finish(old)
        upcoming=self.event('LEAGUE',2)
        generate_bracket(upcoming)
        now=timezone.now()
        upcoming.matches.update(scheduled_start=now+timedelta(minutes=1),scheduled_end=now+timedelta(hours=1))
        self.assertEqual(_scheduled_bracket_event(old,now).pk,old.pk)
        self.assertEqual(_scheduled_bracket_event(old,now+timedelta(minutes=2)).pk,upcoming.pk)
        self.finish(upcoming)
        self.assertEqual(_scheduled_bracket_event(old,now+timedelta(minutes=3)).pk,old.pk)
