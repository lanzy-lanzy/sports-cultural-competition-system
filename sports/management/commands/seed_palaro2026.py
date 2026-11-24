from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from accounts.models import UserProfile
from competitions.models import Competition
from participants.models import Participant
from registrations.models import EventRegistration
from sports.models import EventAward, EventEntry, Match, SportType, SportsEvent, Venue
from sports.services import (
    PALARO_STATIC_EVENTS,
    automatch_with_slots,
    record_match_result,
    resolve_default_tournament_manager,
)
from sports.workflow import confirm_awards, final_match
from teams.models import Department, Team, TeamMembership, TeamStaff


DEPARTMENTS = [
    ('SAFES', 'School of Agriculture, Forestry and Environmental Studies'),
    ('SOCJE', 'School of Criminal Justice Education'),
    ('STE', 'School of Teacher Education'),
    ('SCS', 'School of Computing Studies'),
]

TOURNAMENT_MANAGERS = [
    ('bacalso', 'Jezreel G.', 'Bacalso', 'Bacalso2026!'),
    ('maryjuliet', 'Mary Juliet', 'Doño', 'Maryjuliet2026!'),
    ('mori', 'Allen Day', 'Mori', 'Mori2026!'),
    ('ambalong', 'Nicaster', 'Ambalong', 'Ambalong2026!'),
    ('bascon', 'Carlo Giovanni D.', 'Bascon', 'Bascon2026!'),
    ('cabigas', 'Marjorey', 'Cabigas', 'Cabigas2026!'),
    ('barluado', 'Rob Kellean B.', 'Barluado', 'Barluado2026!'),
    ('lauron', 'Eric', 'Lauron', 'Lauron2026!'),
    ('batucan', 'Hannah', 'Batucan', 'Batucan2026!'),
    ('chatto', 'Vincent John', 'Chatto', 'Chatto2026!'),
    ('canencia', 'Niñobel', 'Canencia', 'Canencia2026!'),
    ('candia', 'Danny Lou C.', 'Candia', 'Candia2026!'),
    ('elardo', 'Helen Grace L.', 'Elardo', 'Elardo2026!'),
    ('matos', 'Zenon A.', 'Matos, Jr.', 'Matos2026!'),
    ('bustamante', 'Ronilo S.', 'Bustamante', 'Bustamante2026!'),
]

DEPARTMENT_TEAMS = [
    {
        'department': 'SAFES',
        'team_name': 'BULLS',
        'color_theme': '#dc2626',
        'description': 'School of Agriculture, Forestry and Environmental Studies official delegation',
        'username': 'safes_manager',
        'password': 'SafesManager2026!',
        'first_name': 'Jamesil',
        'last_name': 'Maputi',
        'players': [
            ('Marco Villanueva', 'male', 20, '09171010001', 1),
            ('Rafael Mendoza', 'male', 21, '09171010002', 2),
            ('Gabriel Santos', 'male', 19, '09171010003', 3),
            ('Paolo Reyes', 'male', 22, '09171010004', 4),
            ('Miguel Bautista', 'male', 20, '09171010005', 5),
            ('Daniel Cruz', 'male', 18, '09171010006', 6),
            ('Joshua Aquino', 'male', 21, '09171010007', 7),
            ('Christian Navarro', 'male', 20, '09171010008', 8),
            ('Andrea Torres', 'female', 19, '09171010009', 9),
            ('Camille Ramos', 'female', 20, '09171010010', 10),
            ('Bianca Flores', 'female', 21, '09171010011', 11),
            ('Patricia Morales', 'female', 18, '09171010012', 12),
            ('Nicole Castillo', 'female', 22, '09171010013', 13),
            ('Katrina Dela Rosa', 'female', 19, '09171010014', 14),
            ('Sophia Lim', 'female', 20, '09171010015', 15),
        ],
    },
    {
        'department': 'STE',
        'team_name': 'PHOENIX',
        'color_theme': '#d97706',
        'description': 'School of Teacher Education official delegation',
        'username': 'ste_manager',
        'password': 'SteManager2026!',
        'first_name': 'Elena',
        'last_name': 'Villanueva',
        'players': [
            ('Adrian Mercado', 'male', 20, '09172010001', 1),
            ('Kenneth Soriano', 'male', 21, '09172010002', 2),
            ('Jericho Alcantara', 'male', 19, '09172010003', 3),
            ('Vincent Pascual', 'male', 22, '09172010004', 4),
            ('Jerome Salcedo', 'male', 20, '09172010005', 5),
            ('Francis Ocampo', 'male', 18, '09172010006', 6),
            ('Carlo Magno', 'male', 21, '09172010007', 7),
            ('Bryan Tolentino', 'male', 20, '09172010008', 8),
            ('Clarisse Domingo', 'female', 19, '09172010009', 9),
            ('Hannah Velasco', 'female', 20, '09172010010', 10),
            ('Denise Aguilar', 'female', 21, '09172010011', 11),
            ('Alyssa Mariano', 'female', 18, '09172010012', 12),
            ('Trisha Panganiban', 'female', 22, '09172010013', 13),
            ('Jasmine Corpuz', 'female', 19, '09172010014', 14),
            ('Michelle Tan', 'female', 20, '09172010015', 15),
        ],
    },
    {
        'department': 'SOCJE',
        'team_name': 'DRAGON',
        'color_theme': '#2563eb',
        'description': 'School of Criminal Justice Education official delegation',
        'username': 'socje_manager',
        'password': 'SocjeManager2026!',
        'first_name': 'Ramon',
        'last_name': 'Dela Cruz',
        'players': [
            ('Dante Valdez', 'male', 21, '09173010001', 1),
            ('Rodel Gutierrez', 'male', 22, '09173010002', 2),
            ('Mark Anthony Perez', 'male', 20, '09173010003', 3),
            ('Jayson Ferrer', 'male', 19, '09173010004', 4),
            ('Arnel Padilla', 'male', 21, '09173010005', 5),
            ('Renzo Cabrera', 'male', 20, '09173010006', 6),
            ('Lester Manalo', 'male', 18, '09173010007', 7),
            ('Noel Sarmiento', 'male', 22, '09173010008', 8),
            ('Maricel Bernardo', 'female', 19, '09173010009', 9),
            ('Angelica Enriquez', 'female', 20, '09173010010', 10),
            ('Shiela Espinoza', 'female', 21, '09173010011', 11),
            ('Kimberly Galang', 'female', 18, '09173010012', 12),
            ('Rhea Javier', 'female', 22, '09173010013', 13),
            ('Lorraine Robles', 'female', 19, '09173010014', 14),
            ('Diana Serrano', 'female', 20, '09173010015', 15),
        ],
    },
    {
        'department': 'SCS',
        'team_name': 'KITSUNE',
        'color_theme': '#15803d',
        'description': 'School of Computing Studies official delegation',
        'username': 'scs_manager',
        'password': 'ScsManager2026!',
        'first_name': 'Clarissa',
        'last_name': 'Navarro',
        'players': [
            ('Ethan Sy', 'male', 20, '09174010001', 1),
            ('Kyle Ong', 'male', 21, '09174010002', 2),
            ('Nathaniel Chua', 'male', 19, '09174010003', 3),
            ('Sean Go', 'male', 22, '09174010004', 4),
            ('Caleb Co', 'male', 20, '09174010005', 5),
            ('Ivan Yu', 'male', 18, '09174010006', 6),
            ('Jared Lao', 'male', 21, '09174010007', 7),
            ('Lucas Ang', 'male', 20, '09174010008', 8),
            ('Chloe Uy', 'female', 19, '09174010009', 9),
            ('Isabelle Dy', 'female', 20, '09174010010', 10),
            ('Samantha Tiu', 'female', 21, '09174010011', 11),
            ('Audrey Wee', 'female', 18, '09174010012', 12),
            ('Mikaela Yap', 'female', 22, '09174010013', 13),
            ('Rachelle See', 'female', 19, '09174010014', 14),
            ('Erica Que', 'female', 20, '09174010015', 15),
        ],
    },
]


class Command(BaseCommand):
    help = 'Seed PALARO 2026 departments, 15 tournament managers, 4 department teams (60 players), and Basketball/Volleyball events.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--reset-competitions',
            action='store_true',
            help='Clear existing competitions, events, matches, entries, and registrations while preserving teams and rosters.',
        )
        parser.add_argument(
            '--simulate-years',
            action='store_true',
            help='Populate simulated intramurals activity across 2026, 2027, and 2028 with scored brackets, consolation matches, and medals.',
        )

    @transaction.atomic
    def handle(self, *args, **options):
        User = get_user_model()
        admin = User.objects.filter(is_superuser=True).order_by('id').first()
        if admin is None:
            admin = User.objects.create_superuser('admin', 'admin@jhcsc.edu.ph', 'Admin2026!')
            profile, _ = UserProfile.objects.get_or_create(user=admin)
            profile.role = UserProfile.Role.ADMINISTRATOR
            profile.save(update_fields=['role', 'updated_at'])

        # 1. Departments
        for code, name in DEPARTMENTS:
            Department.objects.update_or_create(code=code, defaults={'name': name, 'is_active': True})

        # 2. Sport types & static venues from PALARO 2026 catalog
        for spec in PALARO_STATIC_EVENTS:
            SportType.objects.get_or_create(
                name=spec['sport_type'],
                defaults={'team_based': spec['team_based'], 'is_active': True},
            )
            Venue.objects.get_or_create(name=spec['venue_name'], defaults={'is_active': True})

        all_sports = list(SportType.objects.filter(is_active=True))

        # 3. All 15 Tournament Managers
        for uname, fn, ln, pwd in TOURNAMENT_MANAGERS:
            user, _ = User.objects.get_or_create(username=uname, defaults={'first_name': fn, 'last_name': ln, 'is_active': True})
            user.first_name = fn
            user.last_name = ln
            user.is_active = True
            user.set_password(pwd)
            user.save()
            profile, _ = UserProfile.objects.get_or_create(user=user)
            profile.role = UserProfile.Role.TOURNAMENT_MANAGER
            profile.save(update_fields=['role', 'updated_at'])

        # 4. Department Teams, Team Managers & 15 Players each
        for item in DEPARTMENT_TEAMS:
            team = Team.objects.filter(name__iexact=item['team_name']).first()
            if team is None:
                mgr, _ = User.objects.get_or_create(
                    username=item['username'],
                    defaults={'first_name': item['first_name'], 'last_name': item['last_name'], 'is_active': True},
                )
                mgr.first_name = item['first_name']
                mgr.last_name = item['last_name']
                mgr.is_active = True
                mgr.set_password(item['password'])
                mgr.save()
                profile, _ = UserProfile.objects.get_or_create(user=mgr)
                profile.role = UserProfile.Role.TEAM_MANAGER
                profile.save(update_fields=['role', 'updated_at'])

                team = Team.objects.create(
                    name=item['team_name'],
                    department=item['department'],
                    category=Team.Category.SPORTS,
                    color_theme=item['color_theme'],
                    description=item['description'],
                    status=Team.Status.APPROVED,
                    created_by=mgr,
                    roster_submitted=True,
                    roster_submitted_by=mgr,
                    roster_submitted_at=timezone.now(),
                )
                TeamStaff.objects.get_or_create(team=team, user=mgr, role=TeamStaff.Role.MANAGER)
            else:
                if not team.department:
                    team.department = item['department']
                team.color_theme = item['color_theme']
                team.status = Team.Status.APPROVED
                team.save(update_fields=['department', 'color_theme', 'status', 'updated_at'])

            team.sports_categories.set(all_sports)

            for name, gender, age, phone, jersey in item['players']:
                id_no = f"{item['department']}-2026-{jersey:03d}"
                participant = Participant.objects.filter(identification_number=id_no).first()
                if participant is None:
                    participant = Participant.objects.create(
                        name=name,
                        gender=gender,
                        age=age,
                        phone=phone,
                        identification_number=id_no,
                        category='OPEN',
                        status='ACTIVE',
                        team_name=team.name,
                    )
                TeamMembership.objects.get_or_create(
                    team=team,
                    participant=participant,
                    defaults={'member_number': jersey, 'status': TeamMembership.Status.ACTIVE},
                )

        # 5. Competitions & Basketball/Volleyball Events
        if options['reset_competitions']:
            EventAward.objects.all().delete()
            Match.objects.all().delete()
            EventRegistration.objects.all().delete()
            EventEntry.objects.all().delete()
            SportsEvent.objects.all().delete()
            Competition.objects.all().delete()

        now = timezone.now()
        end_dt = now + timedelta(days=7)
        bball_type = SportType.objects.get(name='Basketball')
        vball_type = SportType.objects.get(name='Volleyball')
        bball_venue = Venue.objects.get(name='JHCSC Basketball Court')
        vball_venue = Venue.objects.get(name='JHCSC Campus (Volleyball Court)')

        bball_comp, _ = Competition.objects.get_or_create(
            name='JHCSC INTRAMURAL BASKETBALL 2026',
            defaults={
                'description': 'Official inter-department Basketball tournament (SAFES, STE, SOCJE, SCS).',
                'kind': Competition.Kind.SPORTS,
                'tournament_format': Competition.TournamentFormat.SINGLE_ELIMINATION,
                'status': 'ACTIVE',
                'start_date': now,
                'end_date': end_dt,
                'gold_points': 10,
                'silver_points': 7,
                'bronze_points': 5,
                'created_by': admin,
            },
        )
        vball_comp, _ = Competition.objects.get_or_create(
            name='JHCSC INTRAMURAL VOLLEYBALL 2026',
            defaults={
                'description': 'Official inter-department Volleyball tournament (SAFES, STE, SOCJE, SCS).',
                'kind': Competition.Kind.SPORTS,
                'tournament_format': Competition.TournamentFormat.SINGLE_ELIMINATION,
                'status': 'ACTIVE',
                'start_date': now,
                'end_date': end_dt,
                'gold_points': 10,
                'silver_points': 7,
                'bronze_points': 5,
                'created_by': admin,
            },
        )

        event_specs = [
            (bball_comp, bball_type, 'Basketball - Men', 'male', 15, bball_venue, 'basketball_5x5'),
            (bball_comp, bball_type, 'Basketball - Women', 'female', 15, bball_venue, 'basketball_5x5'),
            (vball_comp, vball_type, 'Volleyball - Men', 'male', 12, vball_venue, 'volleyball'),
            (vball_comp, vball_type, 'Volleyball - Women', 'female', 12, vball_venue, 'volleyball'),
        ]
        for comp, stype, ev_name, gender, req_players, venue, slug in event_specs:
            SportsEvent.objects.update_or_create(
                competition=comp,
                name=ev_name,
                defaults={
                    'sport_type': stype,
                    'category': 'OPEN',
                    'gender': gender,
                    'team_based': True,
                    'format': SportsEvent.Format.SINGLE_ELIMINATION,
                    'players_per_event': req_players,
                    'tournament_manager': resolve_default_tournament_manager(slug, gender),
                    'status': SportsEvent.Status.REGISTRATION,
                    'venue': venue,
                },
            )

        if options['simulate_years']:
            self._simulate_multi_year_intramurals(admin, bball_type, vball_type, bball_venue, vball_venue)

        self.stdout.write(self.style.SUCCESS(
            f'Seeded PALARO 2026: {Department.objects.count()} departments, '
            f'{len(TOURNAMENT_MANAGERS)} tournament managers, '
            f'{Team.objects.exclude(department="").count()} department teams, '
            f'{Competition.objects.count()} competitions, '
            f'{SportsEvent.objects.count()} sports events, '
            f'{Match.objects.count()} matches.'
        ))

    def _simulate_multi_year_intramurals(self, admin, bball_type, vball_type, bball_venue, vball_venue):
        manila = ZoneInfo('Asia/Manila')
        teams_by_name = {
            t.name: t
            for t in Team.objects.filter(name__in=['BULLS', 'PHOENIX', 'DRAGON', 'KITSUNE'], status=Team.Status.APPROVED)
        }
        if len(teams_by_name) < 4:
            return

        yearly_plan = [
            {
                'year': 2026,
                'start': datetime(2026, 11, 16, 8, 0, tzinfo=manila),
                'end': datetime(2026, 11, 21, 17, 0, tzinfo=manila),
                'mode': 'COMPLETE',
                'bball_order': ['BULLS', 'PHOENIX', 'DRAGON', 'KITSUNE'],
                'bball_scores': ((84, 76), (79, 71), (74, 68), (88, 82)),
                'vball_order': ['PHOENIX', 'DRAGON', 'KITSUNE', 'BULLS'],
                'vball_scores': ((3, 1), (3, 2), (3, 0), (3, 2)),
            },
            {
                'year': 2027,
                'start': datetime(2027, 11, 15, 8, 0, tzinfo=manila),
                'end': datetime(2027, 11, 20, 17, 0, tzinfo=manila),
                'mode': 'COMPLETE',
                'bball_order': ['DRAGON', 'KITSUNE', 'BULLS', 'PHOENIX'],
                'bball_scores': ((81, 74), (77, 83), (72, 69), (86, 80)),
                'vball_order': ['KITSUNE', 'BULLS', 'PHOENIX', 'DRAGON'],
                'vball_scores': ((3, 2), (3, 1), (3, 1), (3, 0)),
            },
            {
                'year': 2028,
                'start': datetime(2028, 11, 13, 8, 0, tzinfo=manila),
                'end': datetime(2028, 11, 18, 17, 0, tzinfo=manila),
                'mode': 'PARTIAL',
                'bball_order': ['KITSUNE', 'BULLS', 'PHOENIX', 'DRAGON'],
                'bball_scores': ((78, 73), (82, 75), None, None),
                'vball_order': ['BULLS', 'DRAGON', 'KITSUNE', 'PHOENIX'],
                'vball_scores': (None, None, None, None),
            },
        ]

        for plan in yearly_plan:
            year = plan['year']
            for sport_label, stype, venue, slug, req_players, order, score_plan in [
                ('BASKETBALL 5X5', bball_type, bball_venue, 'basketball_5x5', 15, plan['bball_order'], plan['bball_scores']),
                ('VOLLEYBALL', vball_type, vball_venue, 'volleyball', 12, plan['vball_order'], plan['vball_scores']),
            ]:
                comp_name = f'PALARO {year} - {sport_label}'
                comp, _ = Competition.objects.get_or_create(
                    name=comp_name,
                    defaults={
                        'description': f'Simulated {year} JHCSC Intramurals {sport_label.title()} tournament.',
                        'kind': Competition.Kind.SPORTS,
                        'tournament_format': Competition.TournamentFormat.SINGLE_ELIMINATION,
                        'status': 'ACTIVE',
                        'start_date': plan['start'],
                        'end_date': plan['end'],
                        'gold_points': 10,
                        'silver_points': 7,
                        'bronze_points': 5,
                        'created_by': admin,
                    },
                )
                ev_name = f'{sport_label.title()} ({year}) - Men'
                event, _ = SportsEvent.objects.get_or_create(
                    competition=comp,
                    name=ev_name,
                    defaults={
                        'sport_type': stype,
                        'category': 'OPEN',
                        'gender': 'male',
                        'team_based': True,
                        'format': SportsEvent.Format.SINGLE_ELIMINATION,
                        'players_per_event': req_players,
                        'bronze_policy': 'MATCH',
                        'tournament_manager': resolve_default_tournament_manager(slug, 'male'),
                        'status': SportsEvent.Status.REGISTRATION,
                        'venue': venue,
                        'start_date': plan['start'].date(),
                        'end_date': plan['end'].date(),
                    },
                )

                entries = []
                for tname in order:
                    entry, _ = EventEntry.objects.get_or_create(
                        event=event,
                        team=teams_by_name[tname],
                        defaults={'status': EventEntry.Status.CONFIRMED},
                    )
                    entries.append(entry)

                if not event.matches.exists():
                    automatch_with_slots(
                        event,
                        [e.id for e in entries],
                        venue=venue,
                        start_time=plan['start'],
                        duration_minutes=90,
                        break_minutes=15,
                        include_consolation=True,
                        tournament_format=SportsEvent.Format.SINGLE_ELIMINATION,
                    )

                semis = list(event.matches.filter(round_number=1).order_by('id'))
                if len(semis) == 2:
                    if score_plan[0] and semis[0].status != Match.Status.COMPLETED:
                        record_match_result(semis[0], {1: score_plan[0][0], 2: score_plan[0][1]})
                    if score_plan[1] and semis[1].status != Match.Status.COMPLETED:
                        record_match_result(semis[1], {1: score_plan[1][0], 2: score_plan[1][1]})

                if plan['mode'] == 'COMPLETE':
                    bronze = event.matches.filter(name='Bronze Match').first()
                    final = final_match(event)
                    if bronze and score_plan[2] and bronze.status != Match.Status.COMPLETED:
                        record_match_result(bronze, {1: score_plan[2][0], 2: score_plan[2][1]})
                    if final and score_plan[3] and final.status != Match.Status.COMPLETED:
                        record_match_result(final, {1: score_plan[3][0], 2: score_plan[3][1]})
                    event.refresh_from_db()
                    if not event.confirmed_at:
                        confirm_awards(event, admin)
