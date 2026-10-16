from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.core.files.uploadedfile import SimpleUploadedFile

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
            'email': 'b@a.com', 'phone': '2',
            'age': '25', 'gender': 'male', 'bio': 'x', 'achievements': 'y',
        })
        self.assertRedirects(resp, reverse('participant_list'))
        participant = Participant.objects.get(email='b@a.com')
        self.assertEqual(participant.name, 'Bob C. Doe')

    def test_create_participant_assigns_identity_and_classification(self):
        resp = self.client.post(reverse('create_participant'), {
            'first_name': 'Junior', 'middle_name': 'M.', 'last_name': 'Sample',
            'email': 'junior@example.com', 'phone': '2',
            'age': '16', 'gender': 'female', 'category': 'JUNIOR',
            'team_name': 'Blue Warriors', 'status': 'ACTIVE',
            'identification_type': 'SCHOOL_ID', 'identification_number': 'S-100',
        })

        self.assertRedirects(resp, reverse('participant_list'))
        participant = Participant.objects.get(email='junior@example.com')
        self.assertEqual(participant.name, 'Junior M. Sample')
        self.assertTrue(participant.participant_id.startswith('JHCSC-'))
        self.assertEqual(participant.age_classification, 'Youth')
        self.assertEqual(participant.category, Participant.Category.JUNIOR)
        self.assertEqual(participant.team_name, 'Blue Warriors')

    def test_identification_type_only_offers_school_id(self):
        form = ParticipantForm()
        choices = [value for value, _ in form.fields['identification_type'].choices if value]
        self.assertEqual(choices, [Participant.IdentificationType.SCHOOL_ID])

    def test_identification_type_rejects_other_document_types(self):
        form = ParticipantForm(data={
            'first_name': 'Alex', 'last_name': 'Sample', 'phone': '0917',
            'email': 'alex2@example.com', 'age': '20', 'gender': 'male',
            'category': 'OPEN', 'status': 'ACTIVE',
            'identification_type': 'GOVERNMENT_ID',
        })

        self.assertFalse(form.is_valid())
        self.assertIn('identification_type', form.errors)

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
            'identification_type': '', 'identification_number': '',
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

    def test_identification_document_rejects_unsupported_file_type(self):
        form = ParticipantForm(data={
            'first_name': 'Alex', 'last_name': 'Athlete', 'email': 'alex@example.com',
            'phone': '0917',
            'age': '20', 'gender': 'male', 'category': 'OPEN', 'status': 'ACTIVE',
            'identification_type': 'SCHOOL_ID',
        }, files={
            'identification_document': SimpleUploadedFile('malware.exe', b'not-a-document'),
        })

        self.assertFalse(form.is_valid())
        self.assertIn('identification_document', form.errors)


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
