from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from accounts.models import UserProfile
from participants.models import Participant
from .models import Team, TeamMembership, TeamStaff


class TeamManagementTest(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser('admin', 'admin@example.com', 'pass')
        self.manager = User.objects.create_user('manager', 'manager@example.com', 'pass')
        self.manager.account_profile.role = UserProfile.Role.TEAM_MANAGER
        self.manager.account_profile.save(update_fields=['role', 'updated_at'])
        self.participant = Participant.objects.create(
            name='Alex Athlete', email='athlete@example.com', phone='0917',
            age=20, gender='male', category='OPEN', status='ACTIVE',
        )

    def test_management_can_create_approved_team(self):
        self.client.force_login(self.admin)
        response = self.client.post(reverse('create_team'), {
            'name': 'Blue Warriors', 'category': Team.Category.SPORTS,
            'description': 'College sports team', 'status': Team.Status.APPROVED,
        })

        team = Team.objects.get(name='Blue Warriors')
        self.assertRedirects(response, reverse('team_detail', args=[team.id]))
        self.assertTrue(team.code.startswith('TEAM-'))
        self.assertEqual(team.status, Team.Status.APPROVED)

    def test_team_manager_created_team_is_pending_and_owned(self):
        self.client.force_login(self.manager)
        response = self.client.post(reverse('create_team'), {
            'name': 'Culture Guild', 'category': Team.Category.CULTURAL,
            'description': 'Cultural delegation',
        })

        team = Team.objects.get(name='Culture Guild')
        self.assertRedirects(response, reverse('team_detail', args=[team.id]))
        self.assertEqual(team.status, Team.Status.PENDING)
        self.assertTrue(TeamStaff.objects.filter(
            team=team, user=self.manager, role=TeamStaff.Role.MANAGER,
        ).exists())

    def test_assigned_manager_can_add_roster_member(self):
        team = Team.objects.create(
            name='Blue Warriors', category=Team.Category.SPORTS,
            status=Team.Status.APPROVED, created_by=self.admin,
        )
        TeamStaff.objects.create(team=team, user=self.manager, role=TeamStaff.Role.MANAGER)
        self.client.force_login(self.manager)

        response = self.client.post(reverse('add_team_member', args=[team.id]), {
            'participant': self.participant.id,
            'member_number': 12,
        })

        self.assertRedirects(response, reverse('team_detail', args=[team.id]))
        self.assertTrue(TeamMembership.objects.filter(
            team=team, participant=self.participant, member_number=12,
        ).exists())
        self.participant.refresh_from_db()
        self.assertEqual(self.participant.team_name, 'Blue Warriors')

    def test_team_manager_cannot_access_unassigned_team(self):
        team = Team.objects.create(
            name='Other Team', category=Team.Category.MIXED,
            status=Team.Status.PENDING, created_by=self.admin,
        )
        self.client.force_login(self.manager)
        self.assertEqual(self.client.get(reverse('team_detail', args=[team.id])).status_code, 404)

    def test_management_can_assign_team_manager(self):
        team = Team.objects.create(
            name='Blue Warriors', category=Team.Category.SPORTS,
            status=Team.Status.APPROVED, created_by=self.admin,
        )
        self.client.force_login(self.admin)
        response = self.client.post(reverse('add_team_staff', args=[team.id]), {
            'user': self.manager.id,
            'role': TeamStaff.Role.COACH,
        })

        self.assertRedirects(response, reverse('team_detail', args=[team.id]))
        self.assertTrue(TeamStaff.objects.filter(
            team=team, user=self.manager, role=TeamStaff.Role.COACH,
        ).exists())

    def test_spectator_cannot_access_team_management(self):
        spectator = User.objects.create_user('viewer', 'viewer@example.com', 'pass')
        self.client.force_login(spectator)
        self.assertEqual(self.client.get(reverse('team_list')).status_code, 403)


class AdminTeamApprovalTest(TestCase):
    """A team created by competition management is approved without a status step."""

    def setUp(self):
        self.admin = User.objects.create_superuser('admin', 'admin@example.com', 'pass')
        self.organizer = User.objects.create_user('organizer', 'org@example.com', 'pass')
        self.organizer.account_profile.role = UserProfile.Role.EVENT_ORGANIZER
        self.organizer.account_profile.save(update_fields=['role', 'updated_at'])

    def _create(self, name):
        return self.client.post(reverse('create_team'), {
            'name': name, 'category': Team.Category.SPORTS,
            'description': 'Created in the workspace',
        })

    def test_admin_created_team_is_approved(self):
        self.client.force_login(self.admin)
        response = self._create('Green Wardens')
        team = Team.objects.get(name='Green Wardens')
        self.assertRedirects(response, reverse('team_detail', args=[team.id]))
        self.assertEqual(team.status, Team.Status.APPROVED)

    def test_create_form_omits_the_status_field(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse('create_team'))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'name="status"')
        # The missing control is explained rather than silently dropped.
        self.assertContains(response, 'approved automatically')

    def test_forged_pending_status_in_the_post_is_ignored(self):
        self.client.force_login(self.admin)
        self.client.post(reverse('create_team'), {
            'name': 'Sneaky Squad', 'category': Team.Category.SPORTS,
            'status': Team.Status.PENDING,
        })
        self.assertEqual(
            Team.objects.get(name='Sneaky Squad').status,
            Team.Status.APPROVED,
        )

    def test_forged_suspended_status_is_ignored(self):
        self.client.force_login(self.admin)
        self.client.post(reverse('create_team'), {
            'name': 'Sneakier Squad', 'category': Team.Category.SPORTS,
            'status': Team.Status.SUSPENDED,
        })
        self.assertEqual(
            Team.objects.get(name='Sneakier Squad').status,
            Team.Status.APPROVED,
        )

    def test_other_management_roles_are_auto_approved(self):
        self.client.force_login(self.organizer)
        self.client.post(reverse('create_team'), {
            'name': 'Organizer Crew', 'category': Team.Category.MIXED,
        })
        self.assertEqual(
            Team.objects.get(name='Organizer Crew').status,
            Team.Status.APPROVED,
        )

    def test_team_manager_still_submits_for_approval(self):
        manager = User.objects.create_user('mgr', 'mgr@example.com', 'pass')
        manager.account_profile.role = UserProfile.Role.TEAM_MANAGER
        manager.account_profile.save(update_fields=['role', 'updated_at'])
        self.client.force_login(manager)
        self.client.post(reverse('create_team'), {
            'name': 'Culture Guild', 'category': Team.Category.CULTURAL,
        })
        self.assertEqual(
            Team.objects.get(name='Culture Guild').status,
            Team.Status.PENDING,
        )

    def test_management_can_still_change_status_on_edit(self):
        self.client.force_login(self.admin)
        self._create('Blue Warriors')
        team = Team.objects.get(name='Blue Warriors')

        # Suspending an approved team must remain possible after creation.
        self.client.post(reverse('edit_team', args=[team.id]), {
            'name': team.name, 'category': team.category,
            'description': team.description, 'status': Team.Status.SUSPENDED,
        })
        team.refresh_from_db()
        self.assertEqual(team.status, Team.Status.SUSPENDED)

        # And approving it again.
        self.client.post(reverse('edit_team', args=[team.id]), {
            'name': team.name, 'category': team.category,
            'description': team.description, 'status': Team.Status.APPROVED,
        })
        team.refresh_from_db()
        self.assertEqual(team.status, Team.Status.APPROVED)

    def test_edit_form_still_shows_status(self):
        self.client.force_login(self.admin)
        self._create('Blue Warriors')
        team = Team.objects.get(name='Blue Warriors')
        response = self.client.get(reverse('edit_team', args=[team.id]))
        self.assertContains(response, 'name="status"')

    def test_approved_team_is_selectable_for_sport_entries(self):
        """Approval matters: only approved teams can enter sport events."""
        from competitions.models import Competition
        from sports.forms import EventEntryForm
        from sports.models import SportsEvent, SportType

        self.client.force_login(self.admin)
        self._create('Blue Warriors')
        team = Team.objects.get(name='Blue Warriors')

        competition = Competition.objects.create(
            name='Meet', description='d', status='ACTIVE',
            start_date='2026-01-01 00:00:00', end_date='2026-01-02 00:00:00',
            created_by=self.admin,
        )
        event = SportsEvent.objects.create(
            competition=competition,
            sport_type=SportType.objects.create(name='Basketball', team_based=True),
            name='Basketball', team_based=True,
        )
        form = EventEntryForm(event=event)
        self.assertIn(team, form.fields['team'].queryset)
