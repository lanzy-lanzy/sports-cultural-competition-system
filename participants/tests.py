from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from competitions.models import Competition
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
            'name': 'Bob', 'email': 'b@a.com', 'phone': '2',
            'age': '25', 'gender': 'male', 'bio': 'x', 'achievements': 'y',
        })
        self.assertRedirects(resp, reverse('participant_list'))
        self.assertTrue(Participant.objects.filter(email='b@a.com').exists())

    def test_assign_participants_assigns_with_numbering(self):
        resp = self.client.post(reverse('assign_participants', args=[self.competition.id]), {
            'participants': [self.p1.id],
        })
        self.assertRedirects(resp, reverse('manage_participants', args=[self.competition.id]))
        pc = ParticipantCompetition.objects.get(participant=self.p1, competition=self.competition)
        self.assertEqual(pc.number, 1)
