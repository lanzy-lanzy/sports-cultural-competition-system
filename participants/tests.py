from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.core.files.uploadedfile import SimpleUploadedFile

from competitions.models import Competition
from accounts.models import UserProfile
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
            'team_name': 'College Delegation',
            'identification_type': '', 'identification_number': '',
        })

        self.assertRedirects(response, reverse('my_participant_profile'))
        participant = Participant.objects.get(user=participant_user)
        self.assertEqual(participant.name, 'Alex R. Athlete')
        self.assertEqual(participant.email, 'athlete@example.com')
        self.assertEqual(participant.team_name, 'College Delegation')
        self.assertEqual(participant.age_classification, 'Adult')

    def test_participant_self_service_profile_hides_admin_fields(self):
        form = ParticipantForm(self_service=True)
        for field_name in ('email', 'bio', 'achievements', 'status'):
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
