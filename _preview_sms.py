"""Temporary render check for the redesigned SMS page. Read-only on purpose."""

import os

import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'scoring_system.settings')
django.setup()

from django.test import Client
from django.test.utils import setup_test_environment

setup_test_environment()

from accounts.models import UserProfile
from competitions.models import Competition, Round
from django.contrib.auth.models import User
from django.urls import reverse

admin = User.objects.filter(is_superuser=True).order_by('id').first()
print('admin:', admin, 'cultural competitions:', Competition.objects.filter(
    kind=Competition.Kind.CULTURAL,
).count(), 'rounds:', Round.objects.count())

client = Client()
client.force_login(admin)

for query in ({}, {'scope': 'all'}, {'scope': 'today'}, {'scope': 'all'}):
    response = client.get(reverse('sms_dashboard'), query)
    html = response.content.decode('utf-8')
    print(
        query,
        response.status_code,
        'sports groups:', len(response.context['groups']),
        'cultural groups:', len(response.context['cultural_groups']),
        'sessions:', response.context['row_total'],
        'chips:', [(o['label'][:22], o['count'], o['kind']) for o in response.context['competition_options']],
    )
    if query == {'scope': 'all'}:
        with open('_sms_preview.html', 'w', encoding='utf-8') as handle:
            handle.write(html)

# One cultural card, rendered as the organizer would see it.
cultural = Competition.objects.filter(kind=Competition.Kind.CULTURAL).first()
if cultural:
    url = f"{reverse('sms_dashboard')}?scope=all&competition={cultural.id}"
    response = client.get(url)
    print('cultural filter:', response.status_code, 'groups:', len(response.context['groups']),
          'cultural groups:', len(response.context['cultural_groups']))

print('profiles with role participant:', UserProfile.objects.filter(role='PARTICIPANT').count())
print('players with phone:', __import__('participants.models', fromlist=['Participant']).Participant.objects.exclude(phone='').count())
