from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from competitions.models import Competition
from participants.models import Participant
from accounts.models import UserProfile

from .models import EligibilityRecord


class EligibilityTest(TestCase):
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

    def test_spectator_cannot_open_review_queue(self):
        viewer = User.objects.create_user('viewer', 'v@example.com', 'pass')
        self.client.force_login(viewer)
        self.assertEqual(self.client.get(reverse('eligibility_list')).status_code, 403)

    def test_participant_submits_eligibility_record(self):
        self.client.force_login(self.participant_user)
        resp = self.client.post(reverse('my_eligibility'), {
            'competition': self.competition.id,
            'notes': 'Medical clearance attached.',
        })
        self.assertRedirects(resp, reverse('my_eligibility'))
        record = EligibilityRecord.objects.get(participant=self.participant)
        self.assertEqual(record.status, EligibilityRecord.Status.PENDING)
        self.assertContains(self.client.get(reverse('my_eligibility')), 'Medical clearance attached.')

    def test_approval_links_participant_to_competition(self):
        record = EligibilityRecord.objects.create(
            participant=self.participant,
            competition=self.competition,
        )
        self.client.force_login(self.admin)
        resp = self.client.post(reverse('eligibility_review', args=[record.id]), {'action': 'approve'})
        self.assertRedirects(resp, reverse('eligibility_list') + f'?competition={self.competition.id}')
        record.refresh_from_db()
        self.assertEqual(record.status, EligibilityRecord.Status.APPROVED)
        self.assertEqual(record.reviewed_by, self.admin)
        self.assertTrue(self.competition.participants.filter(id=self.participant.id).exists())

    def test_rejection_does_not_link_participant(self):
        record = EligibilityRecord.objects.create(
            participant=self.participant,
            competition=self.competition,
        )
        self.client.force_login(self.admin)
        self.client.post(reverse('eligibility_review', args=[record.id]), {'action': 'reject', 'notes': 'Missing ID.'})
        record.refresh_from_db()
        self.assertEqual(record.status, EligibilityRecord.Status.REJECTED)
        self.assertFalse(self.competition.participants.filter(id=self.participant.id).exists())
