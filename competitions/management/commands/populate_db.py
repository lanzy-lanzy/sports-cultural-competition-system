import random
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import timedelta

from competitions.models import Competition, Round as CompetitionRound, Criterion
from participants.models import Participant, ParticipantCompetition
from judges.models import Judge, JudgeAssignment
from scoring.models import Score, CompetitionResult
from scoring.services import calculate_rankings


PARTICIPANTS = [
    {
        'name': 'MARIA ANGELICA SANTOS',
        'email': 'maria.angelica.santos@gmail.com',
        'phone': '0917 555 0148',
        'age': 19,
        'gender': 'female',
        'bio': 'A second-year music student from the University of Santo Tomas. Began singing at church choir at age six and has been performing in school productions ever since.',
        'achievements': 'Champion, UST Sing Philippines 2025; 2nd Place, Manila Youth Music Festival 2024',
        'skill': 0.96,
    },
    {
        'name': 'RAFAEL BENEDICTO REYES',
        'email': 'rafael.reyes@gmail.com',
        'phone': '0918 555 0132',
        'age': 23,
        'gender': 'male',
        'bio': 'A freelance vocalist and songwriter from Cebu City who busks at the Ayala terraces every weekend. Known for a warm baritone range.',
        'achievements': 'Semi-finalist, Visayas Got Talent 2024; Original composition featured on regional radio',
        'skill': 0.94,
    },
    {
        'name': 'CAMILA ANDREA FERNANDEZ',
        'email': 'camila.fernandez@gmail.com',
        'phone': '0920 555 0117',
        'age': 18,
        'gender': 'female',
        'bio': 'High school senior and choir president at St. Scholastica\u2019s College. Performs classical crossover and pop repertoire.',
        'achievements': 'Gold Medalist, National Music Competitions for Young Artists 2025',
        'skill': 0.92,
    },
    {
        'name': 'SOFIA ISABELA RAMOS',
        'email': 'sofia.ramos@gmail.com',
        'phone': '0922 555 0175',
        'age': 20,
        'gender': 'female',
        'bio': 'A theater performer from Quezon City with roles in three major stage productions. Combines acting and singing with strong stage charisma.',
        'achievements': 'Best Actress in a Musical, Ateneo Theater Awards 2025',
        'skill': 0.90,
    },
    {
        'name': 'JUAN MIGUEL DELA CRUZ',
        'email': 'juan.delacruz@gmail.com',
        'phone': '0915 555 0193',
        'age': 21,
        'gender': 'male',
        'bio': 'Aged twenty-one, a jeepney driver\u2019s son from Bulacan who sings acoustic covers online. Self-taught guitarist and singer.',
        'achievements': '1M+ streams on original acoustic EP; Featured by a national music blog in 2025',
        'skill': 0.88,
    },
    {
        'name': 'BIANCA NICOLE MENDOZA',
        'email': 'bianca.mendoza@gmail.com',
        'phone': '0919 555 0160',
        'age': 21,
        'gender': 'female',
        'bio': 'A nursing student who moonlights as a wedding singer. Known for soulful interpretations of OPM ballads.',
        'achievements': 'Runner-up, Intramural Singing Contest 2024; Church music ministry soloist',
        'skill': 0.86,
    },
    {
        'name': 'GABRIEL ANDRES VILLANUEVA',
        'email': 'gabriel.villanueva@gmail.com',
        'phone': '0921 555 0129',
        'age': 22,
        'gender': 'male',
        'bio': 'An engineering graduate from Iloilo who pursues music part-time. Competes with a powerful tenor voice.',
        'achievements': 'Champion, West Visayas State University Battle of the Bands 2024',
        'skill': 0.84,
    },
    {
        'name': 'ANDREA KRISTINE SALAZAR',
        'email': 'andrea.salazar@gmail.com',
        'phone': '0916 555 0188',
        'age': 22,
        'gender': 'female',
        'bio': 'A full-time events host and part-time singer from Davao City. Brings polish and professionalism to every performance.',
        'achievements': 'Semi-finalist, Philippine National Singing Competition 2024',
        'skill': 0.82,
    },
    {
        'name': 'LUIS ANTONIO RAMIREZ',
        'email': 'luis.ramirez@gmail.com',
        'phone': '0917 555 0105',
        'age': 24,
        'gender': 'male',
        'bio': 'A call center agent by day and baritone singer by night from Pampanga. Passionate about jazz and bossa nova.',
        'achievements': 'Finalist, Corporate Charity Sing-Off 2025',
        'skill': 0.80,
    },
    {
        'name': 'CHRISTIAN PAOLO NAVARRO',
        'email': 'christian.navarro@gmail.com',
        'phone': '0923 555 0154',
        'age': 20,
        'gender': 'male',
        'bio': 'A college sophomore and campus radio DJ from Laguna. Performs acoustic sets for university events.',
        'achievements': 'Best Interpretation, Laguna Arts Festival 2025',
        'skill': 0.78,
    },
]

JUDGES = [
    {
        'username': 'judge1',
        'email': 'maria.villanueva@gmail.com',
        'first_name': 'Maria',
        'last_name': 'Villanueva',
        'phone': '0917 555 9001',
        'expertise': 'Vocal Performance & Coaching',
        'bio': 'Two-time Awit Award-winning singer and private vocal coach with twenty years of stage experience.',
    },
    {
        'username': 'judge2',
        'email': 'jose.reyes@gmail.com',
        'first_name': 'Jose',
        'last_name': 'Reyes',
        'phone': '0918 555 9002',
        'expertise': 'Music Production & Composition',
        'bio': 'Music producer and composer who has produced chart-topping OPM albums and film soundtracks.',
    },
    {
        'username': 'judge3',
        'email': 'rosario.bautista@gmail.com',
        'first_name': 'Rosario',
        'last_name': 'Bautista',
        'phone': '0919 555 9003',
        'expertise': 'Music Education',
        'bio': 'Professor of Voice at the University of the Philippines Conservatory of Music.',
    },
    {
        'username': 'judge4',
        'email': 'antonio.ramirez@gmail.com',
        'first_name': 'Antonio',
        'last_name': 'Ramirez',
        'phone': '0920 555 9004',
        'expertise': 'Theater Direction & Talent Scouting',
        'bio': 'Theater director and talent scout behind several national stage productions.',
    },
    {
        'username': 'judge5',
        'email': 'lourdes.trinidad@gmail.com',
        'first_name': 'Lourdes',
        'last_name': 'Trinidad',
        'phone': '0921 555 9005',
        'expertise': 'Music Journalism & Broadcasting',
        'bio': 'Seasoned radio broadcaster and music journalist for over fifteen years.',
    },
]

ROUNDS = [
    {
        'name': 'PRELIMINARY ROUND',
        'description': 'Each contestant performs one song of their choice before the panel of judges.',
        'weight': Decimal('30.00'),
        'criteria': [
            {'name': 'VOCAL QUALITY & TONE', 'description': 'Pitch accuracy, tone color, and control of the voice.', 'max': Decimal('40.00')},
            {'name': 'SONG INTERPRETATION', 'description': 'Understanding and expression of the song\u2019s meaning.', 'max': Decimal('30.00')},
            {'name': 'STAGE PRESENCE', 'description': 'Confidence, poise, and connection with the audience.', 'max': Decimal('30.00')},
        ],
    },
    {
        'name': 'SEMIFINAL ROUND',
        'description': 'Contestants perform an OPM classic with live band accompaniment.',
        'weight': Decimal('35.00'),
        'criteria': [
            {'name': 'VOCAL TECHNIQUE & CONTROL', 'description': 'Breath support, dynamics, and technical proficiency.', 'max': Decimal('35.00')},
            {'name': 'EMOTIONAL DELIVERY', 'description': 'Ability to convey emotion and tell a story through song.', 'max': Decimal('35.00')},
            {'name': 'AUDIENCE ENGAGEMENT', 'description': 'Energy, rapport, and ability to hold the audience\u2019s attention.', 'max': Decimal('30.00')},
        ],
    },
    {
        'name': 'GRAND FINALS',
        'description': 'The final showdown featuring the top six contestants. Each performs a show-stopping number.',
        'weight': Decimal('35.00'),
        'criteria': [
            {'name': 'VOCAL PERFORMANCE', 'description': 'Overall vocal excellence and consistency under pressure.', 'max': Decimal('40.00')},
            {'name': 'INTERPRETATION & ARTISTRY', 'description': 'Unique artistic choices and depth of interpretation.', 'max': Decimal('35.00')},
            {'name': 'STAGE PRESENCE & CHARISMA', 'description': 'Star quality, confidence, and command of the stage.', 'max': Decimal('25.00')},
        ],
    },
]

REMARKS = [
    'Outstanding vocal control and phrasing.',
    'Engaging stage presence that connected with the audience.',
    'Excellent dynamics and well-paced performance.',
    'Strong technique with minor pitch issues in the bridge.',
    'Commanding stage presence and confident delivery.',
    'Beautiful tone quality and expressive interpretation.',
    'Slight strain in the higher register but recovered well.',
    'Memorable performance with a unique artistic touch.',
    'Solid performance with room for greater emotional depth.',
    'Impressively consistent across the entire piece.',
]


class Command(BaseCommand):
    help = 'Populates the database with a realistic competition that runs to a declared winner.'

    def handle(self, *args, **kwargs):
        random.seed(2026)

        admin_user, _ = User.objects.get_or_create(
            username='admin',
            defaults={
                'email': 'andrea.delafuente@gmail.com',
                'first_name': 'Andrea',
                'last_name': 'Dela Fuente',
                'is_superuser': True,
                'is_staff': True,
            },
        )
        admin_user.is_superuser = True
        admin_user.is_staff = True
        admin_user.first_name = 'Andrea'
        admin_user.last_name = 'Dela Fuente'
        admin_user.email = 'andrea.delafuente@gmail.com'
        admin_user.set_password('admin123')
        admin_user.save()

        self.clear_existing_data()
        judges = self.create_judges()
        participants = self.create_participants()
        competition = self.create_competition(admin_user)
        self.assign_rounds_and_participants(competition, participants)
        self.assign_judges(competition, judges)
        self.score_competition(competition, judges, participants)
        winner = self.declare_winner(competition, participants)

        self.stdout.write(self.style.SUCCESS(
            f'Competition "{competition.name}" completed. Winner: {winner}'
        ))

    def clear_existing_data(self):
        Score.objects.all().delete()
        CompetitionResult.objects.all().delete()
        ParticipantCompetition.objects.all().delete()
        JudgeAssignment.objects.all().delete()
        Criterion.objects.all().delete()
        CompetitionRound.objects.all().delete()
        Competition.objects.all().delete()
        Participant.objects.all().delete()

    def create_judges(self):
        judges = []
        for data in JUDGES:
            user, _ = User.objects.get_or_create(
                username=data['username'],
                defaults={
                    'email': data['email'],
                    'first_name': data['first_name'],
                    'last_name': data['last_name'],
                },
            )
            user.email = data['email']
            user.first_name = data['first_name']
            user.last_name = data['last_name']
            if not user.password or user.password.startswith('!'):
                user.set_password('judge123')
            user.save()

            judge, _ = Judge.objects.update_or_create(
                user=user,
                defaults={
                    'phone': data['phone'],
                    'expertise': data['expertise'],
                    'bio': data['bio'],
                    'status': 'ACTIVE',
                },
            )
            judges.append(judge)
        return judges

    def create_participants(self):
        participants = []
        for data in PARTICIPANTS:
            participant = Participant.objects.create(
                name=data['name'],
                email=data['email'],
                phone=data['phone'],
                age=data['age'],
                gender=data['gender'],
                bio=data['bio'],
                achievements=data['achievements'],
                status='ACTIVE',
            )
            participants.append((participant, data['skill']))
        return participants

    def create_competition(self, admin_user):
        now = timezone.now()
        return Competition.objects.create(
            name='HIMIG NG BAYAN 2026: NATIONAL SINGING COMPETITION',
            description=(
                'A nationwide search for the country\u2019s most promising young voice. '
                'Contestants compete across three rounds judged by a panel of five industry '
                'professionals. The top six advance to the grand finals, where the grand '
                'champion is declared.'
            ),
            start_date=now - timedelta(days=14),
            end_date=now - timedelta(days=1),
            status='ACTIVE',
            created_by=admin_user,
            show_results=False,
        )

    def assign_rounds_and_participants(self, competition, participants):
        for order, round_data in enumerate(ROUNDS, 1):
            round_obj = CompetitionRound.objects.create(
                competition=competition,
                name=round_data['name'],
                description=round_data['description'],
                order=order,
                status='COMPLETED',
                weight_percentage=round_data['weight'],
            )
            for criterion_data in round_data['criteria']:
                Criterion.objects.create(
                    round=round_obj,
                    name=criterion_data['name'],
                    description=criterion_data['description'],
                    max_score=criterion_data['max'],
                )

        for index, (participant, _) in enumerate(participants, 1):
            ParticipantCompetition.objects.create(
                participant=participant,
                competition=competition,
                number=index,
            )

    def assign_judges(self, competition, judges):
        all_rounds = list(competition.rounds.all())
        for judge in judges:
            assignment = JudgeAssignment.objects.create(
                judge=judge,
                competition=competition,
                status='ACTIVE',
            )
            assignment.rounds.set(all_rounds)

    def score_competition(self, competition, judges, participants):
        for round_obj in competition.rounds.all():
            for criterion in round_obj.criteria.all():
                for participant, skill in participants:
                    for judge in judges:
                        max_score = float(criterion.max_score)
                        base = skill * max_score
                        jitter = random.uniform(-0.015, 0.015) * max_score
                        score_value = max(0.0, min(max_score, base + jitter))
                        Score.objects.create(
                            participant=participant,
                            criterion=criterion,
                            judge=judge,
                            score=Decimal(round(score_value, 1)),
                            remarks=random.choice(REMARKS),
                            status='SUBMITTED',
                        )
            calculate_rankings(round_obj)

    def declare_winner(self, competition, participants):
        competition.status = 'COMPLETED'
        competition.show_results = True
        competition.save()

        weighted_totals = {}
        for participant, _ in participants:
            total = Decimal('0.00')
            for round_obj in competition.rounds.all():
                result = CompetitionResult.objects.filter(
                    competition=competition,
                    participant=participant,
                    round=round_obj,
                ).first()
                if result:
                    total += result.total_score * (round_obj.weight_percentage / Decimal('100'))
            weighted_totals[participant.name] = total

        winner_name = max(weighted_totals, key=weighted_totals.get)
        self.stdout.write('Final weighted standings:')
        for name, total in sorted(weighted_totals.items(), key=lambda x: x[1], reverse=True):
            self.stdout.write(f'  {name}: {total}')
        return winner_name