from decimal import Decimal
from datetime import timedelta

from django.contrib.auth.models import User
from django.utils import timezone

from competitions.models import Competition, Round, Criterion
from participants.models import Participant, ParticipantCompetition
from judges.models import Judge
from teams.models import Team
from scoring.models import Score
from scoring.services import calculate_rankings
from sports.models import SportsEvent, SportType, EventEntry
from sports.services import generate_bracket, record_match_result

admin, _ = User.objects.get_or_create(username='admin', defaults={'is_superuser': True, 'is_staff': True})
admin.is_superuser = True
admin.is_staff = True
admin.set_password('admin123')
admin.save()

now = timezone.now()

sport_comp = Competition.objects.create(
    name='Sports Meet', description='d', status='COMPLETED',
    start_date=now - timedelta(days=10), end_date=now - timedelta(days=5), created_by=admin,
)
sport = SportType.objects.create(name='Basketball', team_based=True)
event = SportsEvent.objects.create(
    competition=sport_comp, sport_type=sport, name='Basketball',
    team_based=True, format=SportsEvent.Format.SINGLE_ELIMINATION,
)
teams = [Team.objects.create(name=f'Sports {i}', category=Team.Category.SPORTS, created_by=admin) for i in range(4)]
for team in teams:
    EventEntry.objects.create(event=event, team=team, status='CONFIRMED')
generate_bracket(event)
for match in event.matches.order_by('round_number', 'id'):
    if match.entries.count() == 2:
        record_match_result(match, {1: 10, 2: 5})

judged = Competition.objects.create(
    name='Singing', description='d', status='COMPLETED',
    kind=Competition.Kind.CULTURAL, cultural_event_type=Competition.CulturalEventType.SINGING,
    start_date=now - timedelta(days=10), end_date=now - timedelta(days=5), created_by=admin,
)
round_obj = Round.objects.create(
    competition=judged, name='Final', description='d', order=1,
    status='COMPLETED', weight_percentage=Decimal('100'),
)
Criterion.objects.create(round=round_obj, name='Craft', description='d', max_score=Decimal('100'))
for i, score in enumerate([Decimal('90'), Decimal('80'), Decimal('70')], start=1):
    participant = Participant.objects.create(
        name=f'Judge P{i}', email=f'p{i}@t.com', phone='0917', age=20, gender='male', status='ACTIVE',
    )
    ParticipantCompetition.objects.create(participant=participant, competition=judged, number=i)
    judge = Judge.objects.create(user=User.objects.create_user(f'j{i}', f'j{i}@t.com', 'pass'))
    Score.objects.create(
        participant=participant, criterion=round_obj.criteria.first(),
        judge=judge, score=score, status='SUBMITTED',
    )
calculate_rankings(round_obj)

print('SEEDED OK')