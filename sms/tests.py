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
from competitions.models import Competition
from participants.models import Participant
from sports.models import EventEntry, Match, MatchEntry, SportsEvent, SportType, Venue
from teams.models import Team, TeamMembership, TeamStaff

from .models import SmsMessage
from .services import (
    build_result_message,
    build_schedule_message,
    describe_summary,
    normalize_phone_number,
    notify_match,
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

    @patch('sms.services.request.urlopen')
    def test_dashboard_sends_test_message(self, urlopen):
        urlopen.return_value = FakeResponse(provider_reply(['09170000000']))
        response = self.client.post(reverse('sms_dashboard'), {
            'action': 'test',
            'number': '09170000000',
            'message': 'Hello from Competrack.',
        })
        self.assertRedirects(response, reverse('sms_dashboard'))
        log = SmsMessage.objects.get()
        self.assertEqual(log.category, SmsMessage.Category.TEST)
        self.assertEqual(log.status, SmsMessage.Status.SENT)

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
