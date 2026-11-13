import io
import json
from datetime import timedelta
from urllib import error, parse
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from accounts.models import UserProfile
from announcements.models import NotificationPreference
from competitions.models import Competition, Round
from participants.models import Participant, ParticipantCompetition
from sports.models import EventEntry, Match, MatchEntry, SportsEvent, SportType, Venue
from teams.models import Team, TeamMembership, TeamStaff

from .models import SmsMessage
from .services import (
    build_cultural_schedule_message,
    build_result_message,
    build_schedule_message,
    describe_summary,
    normalize_phone_number,
    notify_match,
    recipients_for_competition,
    recipients_for_match,
    send_bulk_sms,
    send_sms,
)


class FakeResponse:
    def __init__(self, payload):
        self._body = json.dumps(payload).encode('utf-8')

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def provider_reply(recipients, status='Queued'):
    return [
        {
            'message_id': 1000 + index,
            'recipient': number.replace('0', '63', 1),
            'status': status,
            'sender_name': 'COMPTRACK',
        }
        for index, number in enumerate(recipients)
    ]


def reply_for_queued_numbers(http_request, *args, **kwargs):
    """Echo a delivery record for every number the payload carries."""
    payload = parse.parse_qs(http_request.data.decode('utf-8'))
    return FakeResponse(provider_reply(payload['number'][0].split(',')))


def make_user(username, role=None, phone=''):
    """Create a user and fill in the profile auto-created by accounts.signals."""
    user = User.objects.create_user(username, password='pass')
    profile = user.account_profile
    if role:
        profile.role = role
    profile.phone = phone
    profile.save()
    return user


class PhoneNormalizationTest(TestCase):
    def test_accepts_common_philippine_formats(self):
        for value in ('09171234567', '+63 917 123 4567', '639171234567', '9171234567'):
            self.assertEqual(normalize_phone_number(value), '09171234567')

    def test_rejects_invalid_numbers(self):
        for value in ('', None, '12345', '12345678901', 'abc'):
            self.assertEqual(normalize_phone_number(value), '')


@override_settings(
    SEMAPHORE_API_KEY='test-key',
    SEMAPHORE_SENDER_NAME='COMPTRACK',
    SEMAPHORE_ENABLED=True,
    SEMAPHORE_DRY_RUN=False,
)
class SendSmsTest(TestCase):
    @patch('sms.services.request.urlopen')
    def test_bulk_send_logs_every_recipient(self, urlopen):
        urlopen.return_value = FakeResponse(provider_reply(['09171234567', '09187654321']))
        summary = send_bulk_sms(
            [('0917 123 4567', 'Alex'), ('+63 918 765 4321', 'Bea'), ('12345', 'Bad')],
            'Competrack test message.',
            category=SmsMessage.Category.SCHEDULE,
        )

        self.assertEqual(summary['recipients'], 2)
        self.assertEqual(summary['sent'], 2)
        self.assertEqual(summary['skipped'], 1)
        self.assertEqual(SmsMessage.objects.count(), 2)

        http_request = urlopen.call_args.args[0]
        payload = parse.parse_qs(http_request.data.decode('utf-8'))
        self.assertEqual(payload['apikey'], ['test-key'])
        self.assertEqual(payload['sendername'], ['COMPTRACK'])
        self.assertEqual(payload['number'], ['09171234567,09187654321'])
        self.assertEqual(payload['message'], ['Competrack test message.'])

        log = SmsMessage.objects.get(recipient='09171234567')
        self.assertEqual(log.status, SmsMessage.Status.SENT)
        self.assertEqual(log.provider_status, 'Queued')
        self.assertEqual(log.category, SmsMessage.Category.SCHEDULE)
        self.assertEqual(log.recipient_name, 'Alex')

    @patch('sms.services.request.urlopen')
    def test_test_word_is_prefixed_so_semaphore_does_not_drop_it(self, urlopen):
        urlopen.return_value = FakeResponse(provider_reply(['09171234567']))
        send_sms('09171234567', 'TEST message')
        payload = parse.parse_qs(urlopen.call_args.args[0].data.decode('utf-8'))
        self.assertEqual(payload['message'], ['[Competrack] TEST message'])

    @patch('sms.services.request.urlopen')
    def test_http_error_is_recorded_as_failed(self, urlopen):
        urlopen.side_effect = error.HTTPError(
            'https://api.semaphore.co/api/v4/messages',
            401,
            'Unauthorized',
            {},
            io.BytesIO(b'{"message": "Invalid API key"}'),
        )
        summary = send_sms('09171234567', 'Hello')

        self.assertEqual(summary['sent'], 0)
        self.assertEqual(summary['failed'], 1)
        self.assertIn('Invalid API key', summary['error'])
        log = SmsMessage.objects.get()
        self.assertEqual(log.status, SmsMessage.Status.FAILED)
        self.assertIn('Invalid API key', log.error)

    @override_settings(SEMAPHORE_API_KEY='')
    @patch('sms.services.request.urlopen')
    def test_missing_key_skips_without_calling_semaphore(self, urlopen):
        summary = send_sms('09171234567', 'Hello')

        urlopen.assert_not_called()
        self.assertFalse(summary['configured'])
        self.assertEqual(summary['skipped'], 1)
        self.assertIn('SEMAPHORE_API_KEY', summary['detail'])
        self.assertEqual(SmsMessage.objects.count(), 0)

    @override_settings(SEMAPHORE_DRY_RUN=True)
    @patch('sms.services.request.urlopen')
    def test_dry_run_logs_without_sending(self, urlopen):
        summary = send_sms('09171234567', 'Hello')

        urlopen.assert_not_called()
        self.assertEqual(summary['skipped'], 1)
        log = SmsMessage.objects.get()
        self.assertEqual(log.status, SmsMessage.Status.SKIPPED)
        self.assertEqual(log.provider_status, 'DRY_RUN')


class MatchRecipientsTest(TestCase):
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
        self.team_a = Team.objects.create(name='Team A', category=Team.Category.SPORTS, created_by=self.admin)
        self.team_b = Team.objects.create(name='Team B', category=Team.Category.SPORTS, created_by=self.admin)
        self.match = Match.objects.create(event=self.event, name='Final', round_number=1)
        MatchEntry.objects.create(match=self.match, team=self.team_a, side=1)
        MatchEntry.objects.create(match=self.match, team=self.team_b, side=2)

        self.manager_a = make_user('manager-a', UserProfile.Role.TEAM_MANAGER, '09171234567')
        TeamStaff.objects.create(team=self.team_a, user=self.manager_a, role=TeamStaff.Role.MANAGER)

        self.manager_b = make_user('manager-b', UserProfile.Role.TEAM_MANAGER, '09187654321')
        TeamStaff.objects.create(team=self.team_b, user=self.manager_b, role=TeamStaff.Role.COACH)
        NotificationPreference.objects.create(user=self.manager_b, sms_enabled=False)

    def test_team_match_notifies_only_opted_in_staff(self):
        recipients = recipients_for_match(self.match)
        self.assertEqual(recipients, [('09171234567', 'manager-a (Team A)')])

    def test_team_players_can_be_included(self):
        participant = Participant.objects.create(
            name='Player One', email='player@example.com', phone='09190000000', age=20,
        )
        TeamMembership.objects.create(team=self.team_a, participant=participant)
        recipients = recipients_for_match(self.match, include_team_players=True)
        self.assertIn(('09190000000', 'Player One'), recipients)

    def test_individual_match_notifies_participant(self):
        participant = Participant.objects.create(
            name='Solo Player', email='solo@example.com', phone='09201112222', age=20,
        )
        match = Match.objects.create(event=self.event, name='Singles Final')
        MatchEntry.objects.create(match=match, participant=participant, side=1)
        self.assertEqual(recipients_for_match(match), [('09201112222', 'Solo Player')])

    def test_result_and_schedule_messages_include_details(self):
        entry_a = self.match.entries.get(side=1)
        entry_b = self.match.entries.get(side=2)
        entry_a.score = 78
        entry_a.is_winner = True
        entry_a.save(update_fields=['score', 'is_winner'])
        entry_b.score = 74
        entry_b.save(update_fields=['score'])
        self.match.status = Match.Status.COMPLETED
        self.match.scheduled_start = timezone.now() + timedelta(hours=3)
        self.match.venue = Venue.objects.create(name='JHCSC Gym')
        self.match.save()

        result = build_result_message(self.match)
        self.assertIn('Team A 78 vs Team B 74', result)
        self.assertIn('Winner: Team A', result)

        schedule = build_schedule_message(self.match)
        self.assertIn('Team A vs Team B', schedule)
        self.assertIn('JHCSC Gym', schedule)

    @patch('sms.services.send_bulk_sms')
    def test_notify_match_dispatches_result(self, send_bulk):
        send_bulk.return_value = {'sent': 1}
        notify_match(self.match, 'result')
        send_bulk.assert_called_once()
        args, kwargs = send_bulk.call_args
        self.assertEqual(kwargs['category'], SmsMessage.Category.RESULT)
        self.assertIn('RESULT', args[1])


@override_settings(
    SEMAPHORE_API_KEY='test-key',
    SEMAPHORE_SENDER_NAME='COMPTRACK',
    SEMAPHORE_ENABLED=True,
    SEMAPHORE_DRY_RUN=False,
)
class SmsViewsTest(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser('admin', 'admin@example.com', 'pass')
        self.client.force_login(self.admin)
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
        self.team = Team.objects.create(name='Team A', category=Team.Category.SPORTS, created_by=self.admin)
        self.manager = make_user('manager', UserProfile.Role.TEAM_MANAGER, '09171234567')
        TeamStaff.objects.create(team=self.team, user=self.manager, role=TeamStaff.Role.MANAGER)
        self.match = Match.objects.create(
            event=self.event,
            name='Final',
            round_number=1,
            scheduled_start=timezone.now() + timedelta(hours=2),
        )
        MatchEntry.objects.create(match=self.match, team=self.team, side=1)
        MatchEntry.objects.create(
            match=self.match,
            participant=Participant.objects.create(
                name='Player Two', email='p2@example.com', phone='09187654321', age=20,
            ),
            side=2,
        )

    def test_dashboard_lists_matches_and_has_no_test_form(self):
        Match.objects.create(event=self.event, name='Third Place Game')
        response = self.client.get(reverse('sms_dashboard'), {'scope': 'all'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.competition.name.title())
        self.assertContains(response, 'Basketball - Men')
        self.assertContains(response, 'Team A')
        self.assertContains(response, '2 matches in this view')
        self.assertContains(response, 'Text 2 matches')
        # The gateway is exercised on real schedules now, never on a test blast.
        self.assertNotContains(response, 'name="number"')
        self.assertNotContains(response, 'Send test')

    def test_upcoming_view_hides_schedules_that_already_started(self):
        past = Match.objects.create(
            event=self.event,
            name='Opening Game',
            scheduled_start=timezone.now() - timedelta(hours=5),
        )
        upcoming = self.client.get(reverse('sms_dashboard'))
        self.assertNotContains(upcoming, past.label)
        everything = self.client.get(reverse('sms_dashboard'), {'scope': 'all'})
        self.assertContains(everything, past.label)

    def test_competition_filter_only_accepts_known_competitions(self):
        response = self.client.get(reverse('sms_dashboard'), {
            'scope': 'all', 'competition': self.competition.id,
        })
        self.assertEqual(response.context['selected_competition'], self.competition.id)

        unknown = self.client.get(reverse('sms_dashboard'), {'scope': 'all', 'competition': 987654})
        self.assertIsNone(unknown.context['selected_competition'])
        self.assertContains(unknown, 'Basketball - Men')

    def test_dashboard_shows_log(self):
        SmsMessage.objects.create(recipient='09171234567', body='Hello')
        response = self.client.get(reverse('sms_dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '09171234567')

    @patch('sms.services.request.urlopen')
    def test_match_notify_endpoint(self, urlopen):
        urlopen.return_value = FakeResponse(provider_reply(['09171234567', '09187654321']))
        response = self.client.post(
            reverse('sms_notify_match', args=[self.match.id]),
            {'kind': 'scheduled'},
        )
        self.assertRedirects(response, reverse('match_schedule', args=[self.event.id]))
        self.assertEqual(
            SmsMessage.objects.filter(category=SmsMessage.Category.SCHEDULE).count(),
            2,
        )

    @patch('sms.services.request.urlopen')
    def test_match_notify_returns_to_the_sms_page_when_asked(self, urlopen):
        urlopen.side_effect = reply_for_queued_numbers
        next_url = f"{reverse('sms_dashboard')}?scope=all"
        response = self.client.post(
            reverse('sms_notify_match', args=[self.match.id]),
            {'kind': 'result', 'next': next_url},
        )
        self.assertRedirects(response, next_url)
        self.assertEqual(
            SmsMessage.objects.filter(category=SmsMessage.Category.RESULT).count(),
            2,
        )

    @patch('sms.services.request.urlopen')
    def test_match_notify_ignores_a_foreign_next_url(self, urlopen):
        urlopen.side_effect = reply_for_queued_numbers
        response = self.client.post(
            reverse('sms_notify_match', args=[self.match.id]),
            {'kind': 'scheduled', 'next': 'https://example.com/other-site'},
        )
        self.assertRedirects(
            response,
            reverse('match_schedule', args=[self.event.id]),
            fetch_redirect_response=False,
        )

    @patch('sms.services.request.urlopen')
    def test_bulk_notify_texts_every_match_of_the_competition(self, urlopen):
        urlopen.side_effect = reply_for_queued_numbers
        # A match without entries has nobody to text and must be skipped quietly.
        Match.objects.create(event=self.event, name='Third Place Game')

        response = self.client.post(reverse('sms_bulk_notify'), {
            'competition_id': self.competition.id,
            'kind': 'reminder',
            'scope': 'all',
        })

        self.assertRedirects(
            response, f"{reverse('sms_dashboard')}?scope=all&competition={self.competition.id}",
        )
        self.assertEqual(urlopen.call_count, 1)
        self.assertEqual(
            SmsMessage.objects.filter(category=SmsMessage.Category.REMINDER).count(),
            2,
        )

    @patch('sms.services.request.urlopen')
    def test_bulk_notify_can_target_a_single_event(self, urlopen):
        urlopen.side_effect = reply_for_queued_numbers
        other_competition = Competition.objects.create(
            name='Other Meet',
            description='Second meet',
            start_date='2026-04-01T08:00:00Z',
            end_date='2026-04-02T17:00:00Z',
            status='ACTIVE',
            created_by=self.admin,
        )
        other_event = SportsEvent.objects.create(
            competition=other_competition,
            sport_type=SportType.objects.create(name='Volleyball', team_based=True),
            name='Volleyball - Women',
            team_based=True,
        )
        Match.objects.create(event=other_event, name='Volleyball Final')

        response = self.client.post(reverse('sms_bulk_notify'), {
            'event_id': self.event.id, 'kind': 'scheduled', 'scope': 'all',
        })

        self.assertRedirects(
            response, f"{reverse('sms_dashboard')}?scope=all&competition={self.competition.id}",
        )
        self.assertEqual(
            SmsMessage.objects.filter(category=SmsMessage.Category.SCHEDULE).count(),
            2,
        )

    @patch('sms.services.request.urlopen')
    def test_bulk_notify_rejects_an_unknown_update_type(self, urlopen):
        response = self.client.post(reverse('sms_bulk_notify'), {
            'competition_id': self.competition.id, 'kind': 'test',
        })
        urlopen.assert_not_called()
        self.assertEqual(SmsMessage.objects.count(), 0)
        self.assertRedirects(response, f"{reverse('sms_dashboard')}?scope=upcoming")

    @patch('sms.services.request.urlopen')
    def test_bulk_notify_needs_a_competition_or_event(self, urlopen):
        response = self.client.post(reverse('sms_bulk_notify'), {'kind': 'reminder'})
        urlopen.assert_not_called()
        self.assertRedirects(response, f"{reverse('sms_dashboard')}?scope=upcoming")

    @patch('sms.services.request.urlopen')
    def test_bulk_notify_warns_when_the_view_is_empty(self, urlopen):
        empty = Competition.objects.create(
            name='Empty Meet',
            description='Nothing scheduled',
            start_date='2026-04-01T08:00:00Z',
            end_date='2026-04-02T17:00:00Z',
            status='ACTIVE',
            created_by=self.admin,
        )
        response = self.client.post(reverse('sms_bulk_notify'), {
            'competition_id': empty.id, 'kind': 'reminder', 'scope': 'all',
        })
        urlopen.assert_not_called()
        stored = [str(message) for message in response.wsgi_request._messages]
        self.assertIn('nothing was texted', stored[0])

    @patch('sms.views.MAX_BULK_MATCHES', 1)
    @patch('sms.services.request.urlopen')
    def test_bulk_notify_refuses_more_matches_than_the_limit(self, urlopen):
        Match.objects.create(event=self.event, name='Semifinal')
        response = self.client.post(reverse('sms_bulk_notify'), {
            'competition_id': self.competition.id, 'kind': 'scheduled', 'scope': 'all',
        })
        urlopen.assert_not_called()
        self.assertEqual(SmsMessage.objects.count(), 0)
        stored = [str(message) for message in response.wsgi_request._messages]
        self.assertIn('bulk send can carry', stored[0])


@override_settings(
    SEMAPHORE_API_KEY='test-key',
    SEMAPHORE_SENDER_NAME='COMPTRACK',
    SEMAPHORE_ENABLED=True,
    SEMAPHORE_DRY_RUN=False,
)
class MatchNotificationHooksTest(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser('admin', 'admin@example.com', 'pass')
        self.client.force_login(self.admin)
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
        self.team_a = Team.objects.create(name='Team A', category=Team.Category.SPORTS, created_by=self.admin)
        self.team_b = Team.objects.create(name='Team B', category=Team.Category.SPORTS, created_by=self.admin)
        self.match = Match.objects.create(
            event=self.event,
            name='Final',
            round_number=1,
            scheduled_start=timezone.now() + timedelta(hours=2),
            scheduled_end=timezone.now() + timedelta(hours=3),
        )
        MatchEntry.objects.create(match=self.match, team=self.team_a, side=1)
        MatchEntry.objects.create(match=self.match, team=self.team_b, side=2)

    @patch('sms.services.notify_match')
    def test_edit_match_sends_reschedule_notice(self, notify):
        notify.return_value = {
            'configured': True, 'dry_run': False, 'recipients': 1, 'sent': 1,
            'failed': 0, 'skipped': 0, 'error': '', 'detail': '',
        }
        response = self.client.post(reverse('edit_match', args=[self.match.id]), {
            'name': 'Final',
            'round_number': 1,
            'scheduled_start': '2026-03-02T10:00',
            'scheduled_end': '2026-03-02T11:00',
            'status': Match.Status.SCHEDULED,
            'notes': '',
            'notify_sms': 'on',
        })
        self.assertRedirects(response, reverse('match_schedule', args=[self.event.id]))
        notify.assert_called_once()
        self.assertEqual(notify.call_args.args[1], 'rescheduled')

    def test_edit_match_page_renders_sms_option(self):
        response = self.client.get(reverse('edit_match', args=[self.match.id]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'name="notify_sms"')

    @patch('sms.services.notify_match')
    def test_recording_result_sends_result_notice(self, notify):
        notify.return_value = {
            'configured': True, 'dry_run': False, 'recipients': 1, 'sent': 1,
            'failed': 0, 'skipped': 0, 'error': '', 'detail': '',
        }
        response = self.client.post(reverse('record_match_result', args=[self.match.id]), {
            'score_1': '78',
            'score_2': '74',
            'notes': '',
            'notify_sms': 'on',
        })
        self.assertRedirects(response, reverse('match_schedule', args=[self.event.id]))
        notify.assert_called_once()
        self.assertEqual(notify.call_args.args[1], 'result')

    @patch('sms.services.request.urlopen')
    def test_reminder_command_sends_once_per_schedule(self, urlopen):
        urlopen.return_value = FakeResponse(provider_reply(['09171234567']))
        manager = make_user('manager', UserProfile.Role.TEAM_MANAGER, '09171234567')
        TeamStaff.objects.create(team=self.team_a, user=manager, role=TeamStaff.Role.MANAGER)

        call_command('send_match_reminders', hours=24, verbosity=0)
        self.assertEqual(SmsMessage.objects.filter(category=SmsMessage.Category.REMINDER).count(), 1)

        # The same schedule is not reminded twice.
        call_command('send_match_reminders', hours=24, verbosity=0)
        self.assertEqual(SmsMessage.objects.filter(category=SmsMessage.Category.REMINDER).count(), 1)

    def test_describe_summary(self):
        self.assertEqual(
            describe_summary({'sent': 2, 'failed': 0, 'skipped': 0, 'error': '', 'detail': ''}),
            'SMS sent to 2 recipient(s).',
        )
        self.assertEqual(
            describe_summary({
                'sent': 3, 'failed': 0, 'skipped': 0, 'error': '', 'detail': '',
                'covered': '2 matches',
            }),
            '2 matches covered. SMS sent to 3 recipient(s).',
        )


@override_settings(
    SEMAPHORE_API_KEY='test-key',
    SEMAPHORE_SENDER_NAME='COMPTRACK',
    SEMAPHORE_ENABLED=True,
    SEMAPHORE_DRY_RUN=False,
)
class CulturalSmsServiceTest(TestCase):
    """Socio-cultural events have no matches, so the round is the session."""

    def setUp(self):
        self.admin = User.objects.create_superuser('admin', 'admin@example.com', 'pass')
        self.competition = Competition.objects.create(
            name='Himig Ng Bayan: Solo Singing',
            description='Search for the college voice.',
            kind=Competition.Kind.CULTURAL,
            cultural_event_type=Competition.CulturalEventType.SINGING,
            start_date=timezone.now() + timedelta(days=2),
            end_date=timezone.now() + timedelta(days=2, hours=8),
            status='ACTIVE',
            created_by=self.admin,
        )
        self.preliminary = Round.objects.create(
            competition=self.competition, name='Preliminary Round',
            description='One number per contestant.', order=1, status='PENDING',
        )
        Round.objects.create(
            competition=self.competition, name='Final Round',
            description='The panel decides the champion.', order=2, status='COMPLETED',
        )
        self.solo = Participant.objects.create(
            name='Solo Contestant', email='solo@example.com', phone='09171234567', age=20,
        )
        ParticipantCompetition.objects.create(
            participant=self.solo, competition=self.competition, number=1,
        )
        quiet_user = make_user('quiet', UserProfile.Role.PARTICIPANT, '09187654321')
        NotificationPreference.objects.create(user=quiet_user, sms_enabled=False)
        self.quiet = Participant.objects.create(
            user=quiet_user, name='Quiet Contestant', email='quiet@example.com',
            phone='09187654321', age=21,
        )
        ParticipantCompetition.objects.create(
            participant=self.quiet, competition=self.competition, number=2,
        )

    def test_recipients_are_the_registered_contestants(self):
        self.assertEqual(
            recipients_for_competition(self.competition),
            [('09171234567', 'Solo Contestant')],
        )

    def test_message_names_the_round_and_the_window(self):
        body = build_cultural_schedule_message(self.preliminary)
        self.assertIn('SCHEDULE', body)
        self.assertIn('Preliminary Round', body)
        self.assertIn('Himig Ng Bayan: Solo Singing', body)


@override_settings(
    SEMAPHORE_API_KEY='test-key',
    SEMAPHORE_SENDER_NAME='COMPTRACK',
    SEMAPHORE_ENABLED=True,
    SEMAPHORE_DRY_RUN=False,
)
class CulturalSmsViewsTest(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser('admin', 'admin@example.com', 'pass')
        self.client.force_login(self.admin)
        self.competition = Competition.objects.create(
            name='Himig Ng Bayan',
            description='Solo singing contest',
            kind=Competition.Kind.CULTURAL,
            cultural_event_type=Competition.CulturalEventType.SINGING,
            start_date=timezone.now() + timedelta(days=2),
            end_date=timezone.now() + timedelta(days=2, hours=8),
            status='ACTIVE',
            created_by=self.admin,
        )
        self.preliminary = Round.objects.create(
            competition=self.competition, name='Preliminary Round',
            description='One number per contestant.', order=1, status='PENDING',
        )
        self.final = Round.objects.create(
            competition=self.competition, name='Final Round',
            description='The panel decides the champion.', order=2, status='COMPLETED',
        )
        self.contestant = Participant.objects.create(
            name='Solo Contestant', email='solo@example.com', phone='09171234567', age=20,
        )
        ParticipantCompetition.objects.create(
            participant=self.contestant, competition=self.competition, number=1,
        )
        # A sports competition is kept so both families show up in one view.
        self.sports = Competition.objects.create(
            name='Sports Meet',
            description='Annual sports meet',
            kind=Competition.Kind.SPORTS,
            start_date='2026-03-01T08:00:00Z',
            end_date='2026-03-05T17:00:00Z',
            status='ACTIVE',
            created_by=self.admin,
        )
        event = SportsEvent.objects.create(
            competition=self.sports,
            sport_type=SportType.objects.create(name='Basketball', team_based=True),
            name='Basketball - Men',
            team_based=True,
        )
        self.match = Match.objects.create(
            event=event, name='Final', round_number=1,
            scheduled_start=timezone.now() + timedelta(hours=2),
        )

    def test_dashboard_lists_cultural_rounds_next_to_matches(self):
        response = self.client.get(reverse('sms_dashboard'), {'scope': 'all'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Himig Ng Bayan')
        self.assertContains(response, 'Preliminary Round')
        self.assertContains(response, 'Socio-cultural')
        self.assertContains(response, 'Text 2 rounds')
        self.assertContains(response, 'Basketball - Men')
        self.assertEqual(len(response.context['cultural_groups']), 1)
        self.assertEqual(len(response.context['groups']), 1)

    def test_cultural_competition_is_offered_as_a_filter_chip(self):
        response = self.client.get(reverse('sms_dashboard'))
        chips = {
            option['id']: option['kind']
            for option in response.context['competition_options']
        }
        self.assertEqual(chips[self.competition.id], 'CULTURAL')
        self.assertEqual(chips[self.sports.id], 'SPORTS')

    def test_finished_cultural_competition_is_hidden_from_upcoming(self):
        self.competition.end_date = timezone.now() - timedelta(days=1)
        self.competition.save()
        upcoming = self.client.get(reverse('sms_dashboard'))
        self.assertNotContains(upcoming, 'Preliminary Round')
        everything = self.client.get(reverse('sms_dashboard'), {'scope': 'all'})
        self.assertContains(everything, 'Preliminary Round')

    @patch('sms.services.request.urlopen')
    def test_round_notify_texts_every_registered_contestant(self, urlopen):
        urlopen.side_effect = reply_for_queued_numbers
        response = self.client.post(
            reverse('sms_notify_round', args=[self.preliminary.id]),
            {'kind': 'reminder'},
        )
        self.assertRedirects(
            response, reverse('manage_rounds', args=[self.competition.id]),
        )
        log = SmsMessage.objects.get()
        self.assertEqual(log.recipient, '09171234567')
        self.assertEqual(log.category, SmsMessage.Category.REMINDER)
        self.assertEqual(log.round_id, self.preliminary.id)
        self.assertIsNone(log.match_id)
        self.assertIn('Preliminary Round', log.body)

    @patch('sms.services.request.urlopen')
    def test_round_notify_returns_to_the_sms_page_when_asked(self, urlopen):
        urlopen.side_effect = reply_for_queued_numbers
        next_url = f"{reverse('sms_dashboard')}?scope=all"
        response = self.client.post(
            reverse('sms_notify_round', args=[self.preliminary.id]),
            {'kind': 'scheduled', 'next': next_url},
            follow=False,
        )
        self.assertRedirects(response, next_url, fetch_redirect_response=False)

    @patch('sms.services.request.urlopen')
    def test_bulk_notify_cultural_competition_texts_each_round(self, urlopen):
        urlopen.side_effect = reply_for_queued_numbers
        response = self.client.post(reverse('sms_bulk_notify'), {
            'competition_id': self.competition.id, 'kind': 'scheduled', 'scope': 'all',
        })
        self.assertRedirects(
            response,
            f"{reverse('sms_dashboard')}?scope=all&competition={self.competition.id}",
        )
        # One gateway call per round because every round has its own text.
        self.assertEqual(urlopen.call_count, 2)
        self.assertEqual(
            SmsMessage.objects.filter(category=SmsMessage.Category.SCHEDULE).count(),
            2,
        )

    @patch('sms.services.request.urlopen')
    def test_bulk_notify_cultural_reports_missing_numbers(self, urlopen):
        self.contestant.phone = ''
        self.contestant.save()
        response = self.client.post(reverse('sms_bulk_notify'), {
            'competition_id': self.competition.id, 'kind': 'reminder', 'scope': 'all',
        })
        urlopen.assert_not_called()
        stored = [str(message) for message in response.wsgi_request._messages]
        self.assertIn('have a mobile number on file', stored[0])

