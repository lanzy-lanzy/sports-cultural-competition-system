from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from competitions.models import Competition
from accounts.models import UserProfile
from teams.models import Team, TeamMembership
from .forms import ParticipantForm
from .models import Participant, ParticipantCompetition


class ParticipantViewTest(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser('admin', 'a@a.com', 'pass')
        self.client.login(username='admin', password='pass')
        self.competition = Competition.objects.create(
            name='Comp', description='d', status='ACTIVE',
            start_date='2026-01-01 00:00:00', end_date='2026-01-02 00:00:00',
            created_by=self.admin,
        )
        self.p1 = Participant.objects.create(name='A', email='a@a.com', phone='1', age=20, status='ACTIVE')

    def test_create_participant(self):
        resp = self.client.post(reverse('create_participant'), {
            'first_name': 'Bob', 'middle_name': 'C.', 'last_name': 'Doe',
            'phone': '2', 'identification_number': 'S-200',
            'age': '25', 'gender': 'male', 'bio': 'x', 'achievements': 'y',
        })
        self.assertRedirects(resp, reverse('participant_list'))
        participant = Participant.objects.get(name='Bob C. Doe')
        self.assertEqual(participant.identification_number, 'S-200')

    def test_create_participant_assigns_identity_and_classification(self):
        resp = self.client.post(reverse('create_participant'), {
            'first_name': 'Junior', 'middle_name': 'M.', 'last_name': 'Sample',
            'phone': '2',
            'age': '16', 'gender': 'female', 'category': 'JUNIOR',
            'team_name': 'Blue Warriors', 'status': 'ACTIVE',
            'identification_number': 'S-100',
        })

        self.assertRedirects(resp, reverse('participant_list'))
        participant = Participant.objects.get(name='Junior M. Sample')
        self.assertEqual(participant.name, 'Junior M. Sample')
        self.assertEqual(participant.identification_number, 'S-100')
        self.assertTrue(participant.participant_id.startswith('JHCSC-'))
        self.assertEqual(participant.age_classification, 'Youth')
        self.assertEqual(participant.category, Participant.Category.JUNIOR)
        self.assertEqual(participant.team_name, 'Blue Warriors')

    def test_identification_number_is_captured_as_school_id(self):
        form = ParticipantForm(data={
            'first_name': 'Alex', 'last_name': 'Sample', 'phone': '0917',
            'age': '20', 'gender': 'male',
            'category': 'OPEN', 'status': 'ACTIVE',
            'identification_number': 'S-300',
        })

        self.assertTrue(form.is_valid())
        self.assertEqual(form.cleaned_data['identification_number'], 'S-300')

    def test_participant_form_has_no_email_or_document_fields(self):
        form = ParticipantForm()
        for field_name in ('email', 'identification_type', 'identification_document'):
            self.assertNotIn(field_name, form.fields)
        self.assertIn('identification_number', form.fields)

    def test_assign_participants_assigns_with_numbering(self):
        resp = self.client.post(reverse('assign_participants', args=[self.competition.id]), {
            'participants': [self.p1.id],
        })
        self.assertRedirects(resp, reverse('manage_participants', args=[self.competition.id]))
        pc = ParticipantCompetition.objects.get(participant=self.p1, competition=self.competition)
        self.assertEqual(pc.number, 1)

    def test_roster_panel_renders_for_management(self):
        resp = self.client.get(reverse('roster_panel', args=[self.competition.id]))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Available participants')
        self.assertContains(resp, self.p1.name)

    def test_roster_assign_creates_numbered_assignment(self):
        resp = self.client.post(reverse('roster_assign', args=[self.competition.id]), {
            'participants': [self.p1.id],
        })
        self.assertEqual(resp.status_code, 200)
        pc = ParticipantCompetition.objects.get(participant=self.p1, competition=self.competition)
        self.assertEqual(pc.number, 1)

    def test_roster_assign_is_idempotent(self):
        url = reverse('roster_assign', args=[self.competition.id])
        self.client.post(url, {'participants': [self.p1.id]})
        self.client.post(url, {'participants': [self.p1.id]})
        self.assertEqual(
            ParticipantCompetition.objects.filter(participant=self.p1, competition=self.competition).count(),
            1,
        )

    def test_roster_unassign_removes_assignment(self):
        self.client.post(reverse('roster_assign', args=[self.competition.id]), {'participants': [self.p1.id]})
        resp = self.client.post(reverse('roster_unassign', args=[self.competition.id, self.p1.id]))
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(
            ParticipantCompetition.objects.filter(participant=self.p1, competition=self.competition).exists()
        )

    def test_participant_account_can_maintain_own_participant_profile(self):
        participant_user = User.objects.create_user(
            'athlete', 'athlete@example.com', 'pass',
            first_name='Alex', last_name='Athlete',
        )
        participant_user.account_profile.role = UserProfile.Role.PARTICIPANT
        participant_user.account_profile.save(update_fields=['role', 'updated_at'])
        self.client.force_login(participant_user)

        response = self.client.post(reverse('my_participant_profile'), {
            'first_name': 'Alex', 'middle_name': 'R.', 'last_name': 'Athlete',
            'phone': '0917',
            'age': '20', 'gender': 'prefer_not_to_say', 'category': 'OPEN',
            'identification_number': 'S-500',
        })

        self.assertRedirects(response, reverse('my_participant_profile'))
        participant = Participant.objects.get(user=participant_user)
        self.assertEqual(participant.name, 'Alex R. Athlete')
        self.assertEqual(participant.email, 'athlete@example.com')
        self.assertEqual(participant.age_classification, 'Adult')

    def test_participant_self_service_profile_hides_admin_fields(self):
        form = ParticipantForm(self_service=True)
        for field_name in ('email', 'bio', 'achievements', 'status', 'team_name'):
            self.assertNotIn(field_name, form.fields)
        self.assertNotIn('name', form.fields)
        self.assertIn('first_name', form.fields)

    def test_non_participant_cannot_open_participant_profile(self):
        spectator = User.objects.create_user('viewer', 'viewer@example.com', 'pass')
        self.client.force_login(spectator)
        self.assertEqual(self.client.get(reverse('my_participant_profile')).status_code, 403)


class ParticipantSelfTeamSelectionTest(TestCase):
    def setUp(self):
        self.creator = User.objects.create_user('mgr', 'mgr@example.com', 'pass')
        self.creator.account_profile.role = UserProfile.Role.TEAM_MANAGER
        self.creator.account_profile.save(update_fields=['role', 'updated_at'])

        self.athlete = User.objects.create_user(
            'athlete', 'athlete@example.com', 'pass',
            first_name='Alex', last_name='Athlete',
        )
        self.athlete.account_profile.role = UserProfile.Role.PARTICIPANT
        self.athlete.account_profile.save(update_fields=['role', 'updated_at'])
        self.participant = Participant.objects.create(
            user=self.athlete, name='Alex Athlete', email='athlete@example.com',
            phone='0917', age=20, status='ACTIVE',
        )
        self.approved_team = Team.objects.create(
            name='Blue Warriors', category=Team.Category.SPORTS,
            status=Team.Status.APPROVED, created_by=self.creator,
        )
        self.pending_team = Team.objects.create(
            name='Red Falcons', category=Team.Category.SPORTS,
            status=Team.Status.PENDING, created_by=self.creator,
        )

    def _login_athlete(self):
        self.client.force_login(self.athlete)

    def test_profile_lists_only_approved_teams(self):
        self._login_athlete()
        resp = self.client.get(reverse('my_participant_profile'))
        self.assertContains(resp, 'My team')
        self.assertContains(resp, self.approved_team.name)
        self.assertNotContains(resp, self.pending_team.name)

    def test_participant_can_join_approved_team(self):
        self._login_athlete()
        resp = self.client.post(reverse('select_my_team'), {'team_id': self.approved_team.id})
        self.assertRedirects(resp, reverse('my_participant_profile'))
        membership = TeamMembership.objects.get(participant=self.participant)
        self.assertEqual(membership.team, self.approved_team)
        self.participant.refresh_from_db()
        self.assertEqual(self.participant.team_name, self.approved_team.name)

    def test_participant_cannot_join_pending_team(self):
        self._login_athlete()
        resp = self.client.post(reverse('select_my_team'), {'team_id': self.pending_team.id})
        self.assertRedirects(resp, reverse('my_participant_profile'))
        self.assertFalse(TeamMembership.objects.filter(participant=self.participant).exists())

    def test_joining_new_team_moves_single_membership(self):
        self._login_athlete()
        other = Team.objects.create(
            name='Green Tigers', category=Team.Category.SPORTS,
            status=Team.Status.APPROVED, created_by=self.creator,
        )
        self.client.post(reverse('select_my_team'), {'team_id': self.approved_team.id})
        self.client.post(reverse('select_my_team'), {'team_id': other.id})
        self.assertEqual(TeamMembership.objects.filter(participant=self.participant).count(), 1)
        self.assertEqual(TeamMembership.objects.get(participant=self.participant).team, other)

    def test_participant_can_leave_team(self):
        self._login_athlete()
        TeamMembership.objects.create(team=self.approved_team, participant=self.participant)
        self.participant.team_name = self.approved_team.name
        self.participant.save(update_fields=['team_name'])
        resp = self.client.post(reverse('leave_my_team'))
        self.assertRedirects(resp, reverse('my_participant_profile'))
        self.assertFalse(TeamMembership.objects.filter(participant=self.participant).exists())
        self.participant.refresh_from_db()
        self.assertEqual(self.participant.team_name, '')

    def test_join_requires_post_and_participant_role(self):
        # A participant issuing GET is rejected by require_POST.
        self._login_athlete()
        self.assertEqual(self.client.get(reverse('select_my_team')).status_code, 405)
        # A non-participant is rejected by the role guard.
        self.client.force_login(self.creator)
        self.assertEqual(
            self.client.post(reverse('select_my_team'), {'team_id': self.approved_team.id}).status_code,
            403,
        )


class ParticipantBulkDeleteTest(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser('bulk-admin', 'ba@example.com', 'pass')
        self.competition = Competition.objects.create(
            name='Bulk Comp', description='d', status='ACTIVE',
            start_date='2026-01-01 00:00:00', end_date='2026-01-02 00:00:00',
            created_by=self.admin,
        )
        self.p1 = Participant.objects.create(name='Alice One', email='a1@example.com', phone='1', age=20, status='ACTIVE')
        self.p2 = Participant.objects.create(name='Bob Two', email='b2@example.com', phone='2', age=21, status='ACTIVE')
        self.p3 = Participant.objects.create(name='Cara Three', email='c3@example.com', phone='3', age=22, status='ACTIVE')
        ParticipantCompetition.objects.create(participant=self.p1, competition=self.competition, number=1)
        ParticipantCompetition.objects.create(participant=self.p2, competition=self.competition, number=2)
        ParticipantCompetition.objects.create(participant=self.p3, competition=self.competition, number=3)

    def test_participant_list_renders_bulk_delete_controls(self):
        self.client.force_login(self.admin)
        resp = self.client.get(reverse('participant_list'), {'team': 'unassigned'})
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, reverse('bulk_delete_participants'))
        self.assertContains(resp, 'id="select-all-participants"')
        self.assertContains(resp, 'id="bulk-delete-btn"')

    def test_participant_list_displays_associated_teams_first_then_participants_on_click(self):
        team_alpha = Team.objects.create(
            name='Alpha Eagles', category=Team.Category.SPORTS,
            status=Team.Status.APPROVED, created_by=self.admin,
        )
        team_beta = Team.objects.create(
            name='Beta Tigers', category=Team.Category.SPORTS,
            status=Team.Status.APPROVED, created_by=self.admin,
        )
        TeamMembership.objects.create(team=team_alpha, participant=self.p1)
        TeamMembership.objects.create(team=team_beta, participant=self.p2)

        self.client.force_login(self.admin)
        # Default view: only teams are shown, participant names are hidden until a team is clicked.
        resp = self.client.get(reverse('participant_list'))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Alpha Eagles')
        self.assertContains(resp, 'Beta Tigers')
        self.assertContains(resp, 'Independent / No Team')
        self.assertNotContains(resp, 'Alice One')
        self.assertNotContains(resp, 'Bob Two')
        self.assertNotContains(resp, 'Cara Three')

        # Clicking Alpha Eagles shows only Alice One.
        team_resp = self.client.get(reverse('participant_list'), {'team': str(team_alpha.id)})
        self.assertEqual(team_resp.status_code, 200)
        self.assertContains(team_resp, 'Alpha Eagles')
        self.assertContains(team_resp, 'Alice One')
        self.assertNotContains(team_resp, 'Bob Two')
        self.assertNotContains(team_resp, 'Cara Three')

        # Participant Management hub also displays the associated teams.
        mgmt_resp = self.client.get(reverse('participant_management'))
        self.assertEqual(mgmt_resp.status_code, 200)
        self.assertContains(mgmt_resp, 'Alpha Eagles')
        self.assertContains(mgmt_resp, 'Beta Tigers')
        self.assertNotContains(mgmt_resp, 'Alice One')

    def test_assign_participants_groups_by_team_and_assigns_multiple(self):
        other_comp = Competition.objects.create(
            name='Duo Dance', description='Requires 2+ participants', status='ACTIVE',
            start_date='2026-01-01 00:00:00', end_date='2026-01-02 00:00:00',
            created_by=self.admin,
        )
        team_alpha = Team.objects.create(
            name='Alpha Eagles', category=Team.Category.SPORTS,
            status=Team.Status.APPROVED, created_by=self.admin,
        )
        TeamMembership.objects.create(team=team_alpha, participant=self.p1)
        TeamMembership.objects.create(team=team_alpha, participant=self.p2)

        self.client.force_login(self.admin)
        get_resp = self.client.get(reverse('assign_participants', args=[other_comp.id]))
        self.assertEqual(get_resp.status_code, 200)
        self.assertContains(get_resp, 'Alpha Eagles')
        self.assertContains(get_resp, 'Select all in team')
        group_names = [g['name'] for g in get_resp.context['team_groups']]
        self.assertIn('Alpha Eagles', group_names)

        # Assign 2 participants from Alpha Eagles in one submission.
        post_resp = self.client.post(reverse('assign_participants', args=[other_comp.id]), {
            'participants': [self.p1.id, self.p2.id],
        })
        self.assertRedirects(post_resp, reverse('manage_participants', args=[other_comp.id]))
        self.assertEqual(
            ParticipantCompetition.objects.filter(competition=other_comp, participant_id__in=[self.p1.id, self.p2.id]).count(),
            2,
        )

        # Roster panel also groups remaining available participants by team
        # and labels the assigned participants with their team name.
        panel_resp = self.client.get(reverse('roster_panel', args=[other_comp.id]))
        self.assertEqual(panel_resp.status_code, 200)
        self.assertEqual([g['name'] for g in panel_resp.context['available_team_groups']], ['Independent / No Team'])
        self.assertContains(panel_resp, 'Alpha Eagles')

    def test_bulk_delete_removes_selected_participants_and_audits(self):
        self.client.force_login(self.admin)
        resp = self.client.post(reverse('bulk_delete_participants'), {
            'participant_ids': [self.p1.id, self.p2.id],
        })
        self.assertRedirects(resp, reverse('participant_list'))
        self.assertFalse(Participant.objects.filter(id__in=[self.p1.id, self.p2.id]).exists())
        self.assertTrue(Participant.objects.filter(id=self.p3.id).exists())
        self.assertFalse(ParticipantCompetition.objects.filter(participant_id__in=[self.p1.id, self.p2.id]).exists())
        self.assertTrue(ParticipantCompetition.objects.filter(participant=self.p3).exists())
        from audit.models import AuditLog
        self.assertTrue(AuditLog.objects.filter(action='PARTICIPANT_BULK_DELETED').exists())

    def test_bulk_delete_empty_selection_leaves_participants_intact(self):
        self.client.force_login(self.admin)
        resp = self.client.post(reverse('bulk_delete_participants'), {})
        self.assertRedirects(resp, reverse('participant_list'))
        self.assertEqual(Participant.objects.count(), 3)

    def test_bulk_delete_requires_post_and_management_role(self):
        self.client.force_login(self.admin)
        self.assertEqual(self.client.get(reverse('bulk_delete_participants')).status_code, 405)

        athlete = User.objects.create_user('bulk-athlete', 'athlete@example.com', 'pass')
        athlete.account_profile.role = UserProfile.Role.PARTICIPANT
        athlete.account_profile.save(update_fields=['role', 'updated_at'])
        self.client.force_login(athlete)
        resp = self.client.post(reverse('bulk_delete_participants'), {
            'participant_ids': [self.p1.id],
        })
        self.assertEqual(resp.status_code, 403)
        self.assertEqual(Participant.objects.count(), 3)
