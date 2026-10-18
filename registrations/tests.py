from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from accounts.models import UserProfile
from competitions.models import Competition
from participants.models import Participant, ParticipantCompetition
from sports.models import SportType, SportsEvent
from teams.models import Team, TeamStaff

from .models import EventRegistration


class RegistrationTest(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser('admin', 'a@a.com', 'pass')
        self.competition = Competition.objects.create(
            name='Chess Open',
            description='Annual chess competition',
            start_date='2026-01-10',
            end_date='2026-01-12',
            status='ACTIVE',
            created_by=self.admin,
        )
        self.participant_user = User.objects.create_user('athlete', 'athlete@example.com', 'pass')
        self.participant_user.account_profile.role = UserProfile.Role.PARTICIPANT
        self.participant_user.account_profile.save(update_fields=['role', 'updated_at'])
        self.participant = Participant.objects.create(
            user=self.participant_user,
            name='Anna Santos',
            email='athlete@example.com',
            phone='09170000000',
            age=19,
        )
        self.sport_type = SportType.objects.create(name='Chess', team_based=False)
        self.sport_event = SportsEvent.objects.create(
            competition=self.competition,
            sport_type=self.sport_type,
            name='Chess Singles',
            format=SportsEvent.Format.SINGLE_ELIMINATION,
            status=SportsEvent.Status.SCHEDULED,
        )

    def test_participant_registers_for_sport_event(self):
        self.client.force_login(self.participant_user)
        resp = self.client.post(reverse('register_for_event'), {
            'target_type': 'sport_event',
            'sport_event': self.sport_event.id,
        })
        self.assertRedirects(resp, reverse('my_registrations'))
        registration = EventRegistration.objects.get(registrant=self.participant_user)
        self.assertEqual(registration.participant, self.participant)
        self.assertEqual(registration.sport_event, self.sport_event)
        self.assertEqual(registration.status, EventRegistration.Status.PENDING)

    def test_participant_tracks_approval_status(self):
        EventRegistration.objects.create(
            registrant=self.participant_user,
            participant=self.participant,
            competition=self.competition,
        )
        self.client.force_login(self.participant_user)
        self.assertContains(self.client.get(reverse('my_registrations')), 'Chess Open')
        self.assertContains(self.client.get(reverse('my_registrations')), 'Pending approval')

    def test_spectator_cannot_register(self):
        viewer = User.objects.create_user('viewer', 'v@example.com', 'pass')
        self.client.force_login(viewer)
        self.assertEqual(self.client.get(reverse('register_for_event')).status_code, 403)

    def test_approval_creates_event_entry(self):
        registration = EventRegistration.objects.create(
            registrant=self.participant_user,
            participant=self.participant,
            sport_event=self.sport_event,
            competition=self.competition,
        )
        self.client.force_login(self.admin)
        self.client.post(reverse('registration_review', args=[registration.id]), {'action': 'approve'})
        registration.refresh_from_db()
        self.assertEqual(registration.status, EventRegistration.Status.APPROVED)
        self.assertTrue(self.sport_event.entries.filter(participant=self.participant, status='CONFIRMED').exists())

    def test_approval_with_too_few_entries_does_not_generate_matches(self):
        registration = EventRegistration.objects.create(
            registrant=self.participant_user,
            participant=self.participant,
            sport_event=self.sport_event,
            competition=self.competition,
        )
        self.client.force_login(self.admin)
        self.client.post(reverse('registration_review', args=[registration.id]), {'action': 'approve'})
        self.assertEqual(self.sport_event.matches.count(), 0)

    def test_approval_generates_matches_when_ready(self):
        other_user = User.objects.create_user('athlete2', 'athlete2@example.com', 'pass')
        other_participant = Participant.objects.create(
            user=other_user,
            name='Ben Cruz',
            email='athlete2@example.com',
            age=21,
        )
        EventRegistration.objects.create(
            registrant=self.participant_user,
            participant=self.participant,
            sport_event=self.sport_event,
            competition=self.competition,
        )
        EventRegistration.objects.create(
            registrant=other_user,
            participant=other_participant,
            sport_event=self.sport_event,
            competition=self.competition,
        )
        self.client.force_login(self.admin)
        # First approval: only 1 confirmed entry -> not enough for a bracket.
        self.client.post(
            reverse('registration_review', args=[EventRegistration.objects.get(registrant=self.participant_user).id]),
            {'action': 'approve'},
        )
        self.assertEqual(self.sport_event.matches.count(), 0)
        # Second approval: 2 confirmed entries -> bracket auto-generated.
        self.client.post(
            reverse('registration_review', args=[EventRegistration.objects.get(registrant=other_user).id]),
            {'action': 'approve'},
        )
        matches = list(self.sport_event.matches.all())
        self.assertEqual(len(matches), 1)
        match_entries = list(matches[0].entries.order_by('side'))
        self.assertEqual(
            {match_entries[0].participant_id, match_entries[1].participant_id},
            {self.participant.id, other_participant.id},
        )
        from audit.models import AuditLog
        self.assertTrue(
            AuditLog.objects.filter(
                action='BRACKET_GENERATED',
                details__icontains='auto-generated',
            ).exists(),
        )

    def test_approval_keeps_existing_bracket(self):
        from sports.models import Match
        registration = EventRegistration.objects.create(
            registrant=self.participant_user,
            participant=self.participant,
            sport_event=self.sport_event,
            competition=self.competition,
        )
        # Pre-existing bracket (e.g. seeded) must not be cleared or extended.
        seeded_match = Match.objects.create(event=self.sport_event, name='Round 1')
        self.client.force_login(self.admin)
        self.client.post(reverse('registration_review', args=[registration.id]), {'action': 'approve'})
        from audit.models import AuditLog
        self.assertFalse(
            AuditLog.objects.filter(
                action='BRACKET_GENERATED',
                details__icontains='auto-generated',
            ).exists(),
        )
        self.assertListEqual(list(self.sport_event.matches.order_by('id')), [seeded_match])

    def test_approval_creates_participant_competition(self):
        registration = EventRegistration.objects.create(
            registrant=self.participant_user,
            participant=self.participant,
            competition=self.competition,
        )
        self.client.force_login(self.admin)
        self.client.post(reverse('registration_review', args=[registration.id]), {'action': 'approve'})
        self.assertTrue(ParticipantCompetition.objects.filter(
            participant=self.participant,
            competition=self.competition,
        ).exists())

    def test_rejection_does_not_create_entries(self):
        registration = EventRegistration.objects.create(
            registrant=self.participant_user,
            participant=self.participant,
            sport_event=self.sport_event,
            competition=self.competition,
        )
        self.client.force_login(self.admin)
        self.client.post(reverse('registration_review', args=[registration.id]), {'action': 'reject', 'admin_notes': 'Missing waiver.'})
        registration.refresh_from_db()
        self.assertEqual(registration.status, EventRegistration.Status.REJECTED)
        self.assertFalse(self.sport_event.entries.filter(participant=self.participant).exists())

    def test_team_manager_registers_team(self):
        manager = User.objects.create_user('manager', 'm@example.com', 'pass')
        manager.account_profile.role = UserProfile.Role.TEAM_MANAGER
        manager.account_profile.save(update_fields=['role', 'updated_at'])
        team = Team.objects.create(
            name='Bulldogs',
            category=Team.Category.SPORTS,
            status=Team.Status.APPROVED,
            created_by=manager,
        )
        TeamStaff.objects.create(team=team, user=manager, role=TeamStaff.Role.MANAGER)

        self.client.force_login(manager)
        resp = self.client.post(reverse('register_for_event'), {
            'target_type': 'sport_event',
            'sport_event': self.sport_event.id,
            'team': team.id,
        })
        self.assertRedirects(resp, reverse('my_registrations'))
        self.assertTrue(EventRegistration.objects.filter(registrant=manager, team=team).exists())

    def test_participant_registration_page_has_no_team_dropdown(self):
        # A participant's team comes from "My team"; the redundant dropdown is hidden.
        self.client.force_login(self.participant_user)
        resp = self.client.get(reverse('register_for_event'))
        self.assertEqual(resp.status_code, 200)
        self.assertNotIn('team', resp.context['form'].fields)
        self.assertNotContains(resp, 'name="team"')

    def test_participant_never_sees_team_dropdown_even_if_assigned_as_team_staff(self):
        # Even if a participant account appears in a team's staff list, the
        # registration page keys off the account role: participants never get
        # the team dropdown because their team comes from "My team".
        team = Team.objects.create(
            name='Wildcats', category=Team.Category.SPORTS,
            status=Team.Status.APPROVED, created_by=self.admin,
        )
        TeamStaff.objects.create(team=team, user=self.participant_user, role=TeamStaff.Role.COACH)
        self.client.force_login(self.participant_user)
        resp = self.client.get(reverse('register_for_event'))
        self.assertNotIn('team', resp.context['form'].fields)

    def test_registration_page_has_no_requirements_document_or_notes(self):
        # The register form only captures the event (and team for managers);
        # document uploads and free-text notes were removed from the flow.
        self.client.force_login(self.participant_user)
        resp = self.client.get(reverse('register_for_event'))
        for field_name in ('requirements_document', 'notes'):
            self.assertNotIn(field_name, resp.context['form'].fields)
        self.assertNotContains(resp, 'name="requirements_document"')
        self.assertNotContains(resp, 'name="notes"')

    def test_team_manager_registration_page_shows_team_dropdown(self):
        manager = User.objects.create_user('manager2', 'm2@example.com', 'pass')
        manager.account_profile.role = UserProfile.Role.TEAM_MANAGER
        manager.account_profile.save(update_fields=['role', 'updated_at'])
        team = Team.objects.create(
            name='Bulldogs', category=Team.Category.SPORTS,
            status=Team.Status.APPROVED, created_by=manager,
        )
        TeamStaff.objects.create(team=team, user=manager, role=TeamStaff.Role.MANAGER)
        self.client.force_login(manager)
        resp = self.client.get(reverse('register_for_event'))
        self.assertIn('team', resp.context['form'].fields)
        self.assertContains(resp, 'name="team"')

    def test_start_review_moves_pending_to_under_review(self):
        registration = EventRegistration.objects.create(
            registrant=self.participant_user,
            participant=self.participant,
            sport_event=self.sport_event,
            competition=self.competition,
        )
        self.client.force_login(self.admin)
        self.client.post(reverse('registration_review', args=[registration.id]), {'action': 'review'})
        registration.refresh_from_db()
        self.assertEqual(registration.status, EventRegistration.Status.UNDER_REVIEW)
        self.assertEqual(registration.reviewed_by, self.admin)

    def test_under_review_can_still_be_approved(self):
        registration = EventRegistration.objects.create(
            registrant=self.participant_user,
            participant=self.participant,
            sport_event=self.sport_event,
            competition=self.competition,
            status=EventRegistration.Status.UNDER_REVIEW,
        )
        self.client.force_login(self.admin)
        self.client.post(reverse('registration_review', args=[registration.id]), {'action': 'approve'})
        registration.refresh_from_db()
        self.assertEqual(registration.status, EventRegistration.Status.APPROVED)

    def test_finalized_registration_cannot_be_re_reviewed(self):
        registration = EventRegistration.objects.create(
            registrant=self.participant_user,
            participant=self.participant,
            competition=self.competition,
            status=EventRegistration.Status.APPROVED,
        )
        self.client.force_login(self.admin)
        self.client.post(reverse('registration_review', args=[registration.id]), {'action': 'review'})
        registration.refresh_from_db()
        self.assertEqual(registration.status, EventRegistration.Status.APPROVED)