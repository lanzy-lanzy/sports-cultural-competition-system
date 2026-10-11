"""Seed the sports module with a full intramural sports meet.

Creates sport types, venues, teams with rosters and coaches, individual
athletes, sport events across every bracket format, and a real match schedule
with venues, start/end times, and recorded results.

Run it with::

    .venv\\Scripts\\python.exe manage.py seed_sports

Useful flags::

    --flush              wipe existing sports data before seeding
    --reset-matches      rebuild brackets, schedule, and results only
    --competition <ref>  attach the events to an existing competition (id or name)
    --seed <int>         random seed for reproducible scores
    --quiet              print only the final summary
"""

import random
from collections import OrderedDict
from datetime import datetime, time, timedelta

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from accounts.models import UserProfile
from competitions.models import Competition
from participants.models import Participant, ParticipantCompetition
from teams.models import Team, TeamMembership, TeamStaff

from sports.models import EventEntry, Match, SportsEvent, SportType, Venue
from sports.services import generate_bracket, record_match_result


SPORT_TYPES = [
    ('Basketball', True, 'Five-a-side court sport played with a size 7 ball.'),
    ('Volleyball', True, 'Indoor or outdoor court sport, best of three sets.'),
    ('Sepak Takraw', True, 'Traditional Filipino net sport played with a rattan ball.'),
    ('Table Tennis', True, 'Doubles and team events played on a table tennis table.'),
    ('Esports', True, 'Mobile Legends and other competitive game titles.'),
    ('Badminton', False, 'Racquet sport, best of three games to 21 points.'),
    ('Chess', False, 'Individual board sport, two rapid games per match.'),
    ('Athletics', False, 'Track and field events timed on the oval.'),
]

VENUES = [
    ('Main Gymnasium', 'Main Campus, North Wing', 1500,
     'Indoor basketball court with retractable bleachers.'),
    ('Covered Court', 'Engineering Building, Ground Floor', 800,
     'Covered multi-purpose court used for volleyball and futsal.'),
    ('Sepak Takraw Courts', 'Sports Complex, Court 3-4', 400,
     'Two regulation sepak takraw courts with the net at 1.52 metres.'),
    ('Table Tennis Hall', 'Gymnasium Mezzanine', 300,
     'Twelve table tennis tables in an air conditioned hall.'),
    ('Badminton Indoor Court', 'Sports Complex, Court 5', 250,
     'Three indoor courts with proper lighting and sprung flooring.'),
    ('Athletics Oval', 'Back Field, 400m Track', 2000,
     'Standard 400 metre eight lane tartan track.'),
    ('Function Room A', 'Academic Building, 2nd Floor', 120,
     'Air conditioned function room used for chess.'),
    ('Computer Laboratory 2', 'IT Building, 2nd Floor', 60,
     'Laboratory with 40 workstations for esports events.'),
]

TEAMS = [
    ('Green Warriors', 'green', 'Athletic delegation with real depth at basketball and volleyball.'),
    ('Crimson Tide', 'red', 'Recruited mostly from the engineering program.'),
    ('Azure Falcons', 'blue', 'Fast breaks and an aggressive pressing defence.'),
    ('Golden Suns', 'gold', 'Consistent performers who always clear the group stage.'),
    ('Violet Vipers', 'purple', 'Led by the reigning campus chess champion.'),
    ('Royal Knights', 'navy', 'A very strong serving team in volleyball.'),
    ('Cobalt Comets', 'teal', 'New program working toward a semifinal berth.'),
    ('Scarlet Stallions', 'maroon', 'Heavily supported by the criminology block.'),
    ('Jade Jaguars', 'forest', 'Athletics powerhouse with sepak takraw veterans.'),
    ('Orange Octopus', 'orange', 'Esports squad that also fields a sepak takraw side.'),
    ('Pearl Panthers', 'white', 'Table tennis specialists who train after class.'),
    ('Maroon Marauders', 'maroon', 'Mixed delegation with an open roster policy.'),
]

# Five roster members per team, in jersey number order.
TEAM_MEMBERS = [
    ['KENNETH ABAD SANTOS', 'MARC ANTHONY DELA CRUZ', 'JOSHUA RAYMOND PEREZ',
     'EMMANUEL JAY VILLANUEVA', 'NIKO PATRICK GARCIA'],
    ['DANIEL FRANCIS LOPEZ', 'PATRICK GERALD MENDOZA', 'JOHN MARK RAMOS',
     'JERICHO SANTOS BAUTISTA', 'ADRIAN CRUZ TALA'],
    ['RODNEY MAGNO SANTOS', 'JAYVEE DE GUZMAN', 'KENNETH VINCENT MALINAO',
     'ALVIN DELA ROSA', 'MICHAEL ANGELO AQUINO'],
    ['LEONARDO CRUZ PAGTAKAS', 'FRANCIS GERALD TIONG', 'JOHANN ORTIZ RAMOS',
     'RICHARD MAGNO ALBERTO', 'STEVEN PAOLO LIM'],
    ['ISAAC MANUEL SANTOS', 'GREGORY DE GUZMAN REYES', 'CARLO MIGUEL DELOS SANTOS',
     'BENJAMIN LEE GUTIERREZ', 'JOSHUA MAR VILLANUEVA'],
    ['OMAR PATRICK BENEDICTO', 'IAN JOSEPH SANTOS', 'DAVID MIGUEL MANALO',
     'EDWARD LOPEZ CASTRO', 'RAYMOND DELOS SANTOS'],
    ['ALLEN DEL CRUZ REYES', 'BRYAN SANTOS DIMACULANG', 'CEDRIC MAGNO MALALAG',
     'DENVER SANTOS PASCUAL', 'ERNIELITO SANTOS RAMOS'],
    ['ROMEO DE GUZMAN SANTOS', 'MARVIN PATRICK DE LEON', 'NERWIN BERMUDEZ SANTOS',
     'OSMAN TALA MENDOZA', 'PETER JOHN VILLARIN'],
    ['ROLAND MATTHEW SANTOS', 'SANTOS MIGUEL DE GUIA', 'TEODORO VARGAS LIM',
     'VALENTIN CRUZ BOCALING', 'WILSON SANTOS TIONG'],
    ['XAVIER ROMERO DELOS SANTOS', 'YVES PATRICK GARCIA', 'ZENO CRUZ MAGNO',
     'AARON PAOLO SANTOS', 'BENIGN ABEL GARCIA'],
    ['CHRISTIAN GERARD REYES', 'DARRIN PAOLO SANTOS', 'EDWIN DE GUZMAN MAGNO',
     'FLORIAN CRUZ REYES', 'GABRIEL TALA SANTOS'],
    ['HAROLD CRUZ DELOS SANTOS', 'IVAN PAOLO MAGNO', 'JAYPEE SANTOS GARCIA',
     'KENNETH DELA CRUZ RAMOS', 'LOUIS PATRICK DELOS REYES'],
]

COACHES = [
    ('coach_cruz', 'Rafael', 'Cruz', '0917 555 7101'),
    ('coach_reyes', 'Analyn', 'Reyes', '0918 555 7102'),
    ('coach_santos', 'Bernardo', 'Santos', '0919 555 7103'),
    ('coach_lim', 'Charisse', 'Lim', '0920 555 7104'),
]

INDIVIDUAL_ATHLETES = [
    ('MARIA ANGELICA DELA CRUZ', 'male', 20, 'Chess national par time finalist.'),
    ('JOSE MARIA SANTOS', 'male', 22, 'Rook end specialist rated 2100 by FIDE.'),
    ('ANGELA ROSE RAMOS', 'female', 19, 'Back end player, campus champion 2025.'),
    ('MARK ANTHONY CRUZ', 'male', 21, 'Known for the Sicilian Najdorf attack.'),
    ('KRISTINE MAE SANTOS', 'female', 20, 'National athletics sprint finalist.'),
    ('JOHN PAUL DELOS SANTOS', 'male', 23, 'Chess and mathematics double major.'),
    ('BEATRICE LOPEZ', 'female', 18, 'Youngest player in the open division.'),
    ('RICARDO MENDEZ SANTOS', 'male', 24, 'Rapid chess provincial medalist.'),
    ('CLARISSE ANNE REYES', 'female', 21, 'Badminton bronze at the regional meet.'),
    ('DANILO CRUZ MAGNO', 'male', 22, 'Doubles specialist with a strong backhand.'),
    ('ELAINE JOY DELOS SANTOS', 'female', 20, 'Ranked second on the women singles ladder.'),
    ('FRANCIS GERALD LIM', 'male', 25, 'Faculty player and assistant coach.'),
    ('GRACE ANNE SANTOS', 'female', 19, 'Quarter finalist in last year open.'),
    ('HUGO MIGUEL RAMOS', 'male', 23, 'Table tennis convert turned badminton player.'),
]

COMPETITION_NAME = 'JHCSC INTRAMURAL SPORTS MEET 2026'
COMPETITION_DESCRIPTION = (
    'The annual intramural sports meet of J.H. Cerilles State College. Nine sport '
    'events run across eight venues over eleven days, with team and individual '
    'divisions, group stages, and knockout brackets for every medal.'
)

MATCH_NOTES = [
    'Officiated by the assigned referee crew.',
    'Clean match, no formal protests filed.',
    'Weather advisory cleared before tip off.',
    'Recorded on the official match sheet.',
    'Score verified by the sports coordinator.',
]


class EventSpec:
    """Declarative description of one seeded sport event."""

    def __init__(self, key, sport, name, gender, category, event_format, team_based,
                 venue, day_offset, days, duration, turnaround, contestants,
                 max_teams, win_scores, lose_scores, rules, notes):
        self.key = key
        self.sport = sport
        self.name = name
        self.gender = gender
        self.category = category
        self.format = event_format
        self.team_based = team_based
        self.venue = venue
        self.day_offset = day_offset
        self.days = days
        self.duration = duration
        self.turnaround = turnaround
        self.contestants = contestants
        self.max_teams = max_teams
        self.win_scores = win_scores
        self.lose_scores = lose_scores
        self.rules = rules
        self.notes = notes


EVENT_SPECS = [
    EventSpec(
        key='basketball_men', sport='Basketball', name='Basketball - Men',
        gender='male', category='OPEN',
        event_format=SportsEvent.Format.SINGLE_ELIMINATION, team_based=True,
        venue='Main Gymnasium', day_offset=0, days=2, duration=100, turnaround=40,
        contestants=('teams', 8), max_teams=16,
        win_scores=(78, 96), lose_scores=(56, 78),
        rules=('FIBA rules. Four 10-minute quarters, a 2 minute break between '
               'quarters and a 15 minute half time. A 5 minute overtime is '
               'played if tied at the end of regulation.'),
        notes='Seeded from the district qualifying ladder.',
    ),
    EventSpec(
        key='basketball_women', sport='Basketball', name='Basketball - Women',
        gender='female', category='OPEN',
        event_format=SportsEvent.Format.ROUND_ROBIN, team_based=True,
        venue='Covered Court', day_offset=1, days=2, duration=90, turnaround=30,
        contestants=('teams', 4), max_teams=8,
        win_scores=(68, 88), lose_scores=(48, 66),
        rules='FIBA rules with four 8-minute quarters to keep the round robin on schedule.',
        notes='Single round robin, top two advance to the medal round.',
    ),
    EventSpec(
        key='volleyball_men', sport='Volleyball', name='Volleyball - Men',
        gender='male', category='OPEN',
        event_format=SportsEvent.Format.GROUP_STAGE, team_based=True,
        venue='Covered Court', day_offset=2, days=3, duration=75, turnaround=25,
        contestants=('teams', 8), max_teams=12,
        win_scores=(72, 94), lose_scores=(58, 70),
        rules=('Best of three sets to 25 points, deciding set to 15. Rally '
               'scoring with a technical timeout at 8 points in the first two sets.'),
        notes='Four groups of two, then a knockout stage for the top two.',
    ),
    EventSpec(
        key='sepak_takraw', sport='Sepak Takraw', name='Sepak Takraw - Open',
        gender='mixed', category='OPEN',
        event_format=SportsEvent.Format.DOUBLE_ELIMINATION, team_based=True,
        venue='Sepak Takraw Courts', day_offset=3, days=3, duration=70, turnaround=25,
        contestants=('teams', 4), max_teams=8,
        win_scores=(21, 25), lose_scores=(13, 20),
        rules=('Regulations of the Sepak Takraw Association of the Philippines. '
               'Best of three regular sets, with a fourth set played to 15.'),
        notes='Winners bracket, losers bracket, then a grand final.',
    ),
    EventSpec(
        key='table_tennis', sport='Table Tennis', name='Table Tennis - Team',
        gender='open', category='OPEN',
        event_format=SportsEvent.Format.GROUP_STAGE, team_based=True,
        venue='Table Tennis Hall', day_offset=4, days=3, duration=60, turnaround=15,
        contestants=('teams', 8), max_teams=12,
        win_scores=(11, 21), lose_scores=(6, 18),
        rules=('Team tie is two singles and one doubles match, best of three '
               'games to 11 points, on a 10 minute cycle.'),
        notes='Group stage, then a knockout stage for the top two of each group.',
    ),
    EventSpec(
        key='esports', sport='Esports', name='Esports - MLBB Open',
        gender='open', category='OPEN',
        event_format=SportsEvent.Format.SINGLE_ELIMINATION, team_based=True,
        venue='Computer Laboratory 2', day_offset=5, days=2, duration=120, turnaround=20,
        contestants=('teams', 8), max_teams=16,
        win_scores=(2, 3), lose_scores=(0, 1),
        rules=('Mobile Legends Bang Bang, best of three games on the Honor of '
               'Kings map pool. Each team bans two heroes in the draft.'),
        notes='Quarterfinals through the grand final, streamed on the college channel.',
    ),
    EventSpec(
        key='chess', sport='Chess', name='Chess - Open Division',
        gender='open', category='OPEN',
        event_format=SportsEvent.Format.SINGLE_ELIMINATION, team_based=False,
        venue='Function Room A', day_offset=6, days=2, duration=50, turnaround=10,
        contestants=('participants', 8), max_teams=16,
        win_scores=(1, 1), lose_scores=(0, 0),
        rules=('Two rapid games of 10 minutes plus 5 seconds per move. Draws are '
               'broken by a 5 minute sudden death blitz.'),
        notes='Individual entries, no team affiliation required.',
    ),
    EventSpec(
        key='badminton', sport='Badminton', name='Badminton - Women Singles',
        gender='female', category='OPEN',
        event_format=SportsEvent.Format.ROUND_ROBIN, team_based=False,
        venue='Badminton Indoor Court', day_offset=7, days=2, duration=55, turnaround=15,
        contestants=('participants', 6), max_teams=12,
        win_scores=(21, 22), lose_scores=(13, 19),
        rules='Best of three games to 21 points, win by two, third game to 11 at 20 all.',
        notes='Round robin determines the podium directly.',
    ),
    EventSpec(
        key='athletics', sport='Athletics', name='Athletics - Track & Field',
        gender='open', category='OPEN',
        event_format=SportsEvent.Format.SINGLE_ELIMINATION, team_based=True,
        venue='Athletics Oval', day_offset=9, days=2, duration=60, turnaround=0,
        contestants=('teams', 0), max_teams=None,
        win_scores=(1, 1), lose_scores=(0, 0),
        rules=('100m, 400m, 800m, 1500m, long jump, high jump, shot put, and '
               'the 4x100m relay. Trials are held the day before the finals.'),
        notes='Entries remain open until the meet. Seeded without a bracket.',
    ),
]


def _round_up(value, minutes):
    """Round ``value`` up to the next ``minutes`` mark past the hour."""
    floor = value.replace(second=0, microsecond=0)
    remainder = floor.minute % minutes
    if remainder == 0:
        return floor
    return floor + timedelta(minutes=minutes - remainder)


class ScheduleBoard:
    """Books matches into venue lanes so no two matches overlap inside a venue."""

    def __init__(self, venues, day_open=time(8, 0), day_close=time(18, 0)):
        self.day_open = day_open
        self.day_close = day_close
        self.lanes = OrderedDict((venue.id, {'venue': venue, 'busy': []}) for venue in venues)

    def _conflicts(self, lane, start, end):
        return [(booked_start, booked_end) for booked_start, booked_end in lane['busy']
                if start < booked_end and end > booked_start]

    def _next_open(self, value):
        """Push ``value`` to the next day opening when it falls outside play hours."""
        if value.time() >= self.day_close:
            following = (value + timedelta(days=1)).replace(
                hour=self.day_open.hour, minute=self.day_open.minute,
                second=0, microsecond=0,
            )
            return following
        if value.time() < self.day_open:
            return value.replace(
                hour=self.day_open.hour, minute=self.day_open.minute,
                second=0, microsecond=0,
            )
        return value

    def _lane_order(self, preferred_id):
        """Home venue first, then the remaining venues in a stable rotation."""
        if preferred_id in self.lanes:
            rest = [lane_id for lane_id in self.lanes if lane_id != preferred_id]
            return [preferred_id] + rest
        return list(self.lanes)

    def book(self, earliest, duration, deadline=None, turnaround=20, preferred_id=None):
        """Reserve the earliest free slot of ``duration`` minutes from ``earliest``.

        Matches are offered to the event's home venue first and fall back to the
        other venues only when that one is already busy, so matches in the same
        round still run in parallel. Returns ``(start, end, venue)`` or None.
        """
        gap = timedelta(minutes=turnaround)
        for lane_id in self._lane_order(preferred_id):
            lane = self.lanes[lane_id]
            start = self._next_open(earliest)
            for _ in range(400):
                start = _round_up(self._next_open(start), 15)
                end = start + timedelta(minutes=duration)
                if end.time() > self.day_close or end.date() != start.date():
                    start = self._next_open(start + timedelta(minutes=15))
                    continue
                conflicts = self._conflicts(lane, start, end)
                if not conflicts:
                    break
                start = max(booked_end for _, booked_end in conflicts) + gap
            else:
                continue
            if deadline is not None and end > deadline:
                continue
            lane['busy'].append((start, end))
            return start, end, lane['venue']
        return None

    def overlaps(self):
        """Return ``(venue, (start, end), (start, end))`` for every double booking."""
        found = []
        for lane in self.lanes.values():
            ordered = sorted(lane['busy'])
            for index, (start, end) in enumerate(ordered):
                for other_start, other_end in ordered[index + 1:]:
                    if other_start >= end:
                        break
                    found.append((lane['venue'], (start, end), (other_start, other_end)))
        return found


class Command(BaseCommand):
    help = 'Seeds sport types, venues, teams, athletes, events, brackets, and a match schedule.'

    def add_arguments(self, parser):
        parser.add_argument('--flush', action='store_true',
                            help='Delete existing sports data before seeding.')
        parser.add_argument('--reset-matches', action='store_true',
                            help='Rebuild brackets, schedule, and results for seeded events only.')
        parser.add_argument('--competition', dest='competition', default='',
                            help='Competition id or exact name to attach the events to.')
        parser.add_argument('--seed', type=int, default=2026,
                            help='Random seed so scores stay reproducible.')
        parser.add_argument('--quiet', action='store_true',
                            help='Print only the final summary.')

    def handle(self, *args, **options):
        random.seed(options['seed'])
        quiet = options['quiet']

        def log(message):
            if not quiet:
                self.stdout.write(message)

        with transaction.atomic():
            if options['flush']:
                self._flush()
                log('Cleared existing sports data.')

            admin = self._ensure_admin()
            competition = self._ensure_competition(admin, options['competition'])
            sport_types = self._create_sport_types()
            venues = self._create_venues()
            coaches = self._create_coaches()
            self._create_teams(admin, coaches)
            athletes = self._create_athletes(competition)

            board = ScheduleBoard(venues.values())
            events = self._create_events(competition, sport_types, venues)
            log(f'Seeding {len(events)} events for "{competition.name}":')
            for event in events:
                self._seed_event(event, board, athletes, log)

            self._sync_competition(competition)

        overlaps = board.overlaps()
        if overlaps:
            self.stdout.write(self.style.WARNING(
                f'{len(overlaps)} venue overlap(s) detected in the generated schedule.'
            ))
        self.stdout.write(self.style.SUCCESS(
            'Sports seed complete: '
            f'{SportType.objects.count()} sport types, {Venue.objects.count()} venues, '
            f'{Team.objects.count()} teams, {SportsEvent.objects.count()} events, '
            f'{Match.objects.count()} matches '
            f'({Match.objects.filter(status=Match.Status.COMPLETED).count()} completed, '
            f'{Match.objects.filter(status=Match.Status.SCHEDULED).count()} still to play).'
        ))

    # ------------------------------------------------------------------
    # Reference data
    # ------------------------------------------------------------------
    def _flush(self):
        Match.objects.all().delete()
        EventEntry.objects.all().delete()
        SportsEvent.objects.all().delete()
        Venue.objects.all().delete()
        SportType.objects.all().delete()
        TeamStaff.objects.all().delete()
        TeamMembership.objects.all().delete()
        Team.objects.all().delete()

    def _ensure_admin(self):
        admin, _ = User.objects.get_or_create(
            username='admin',
            defaults={
                'email': 'andrea.delafuente@gmail.com',
                'first_name': 'Andrea',
                'last_name': 'Dela Fuente',
                'is_staff': True,
                'is_superuser': True,
            },
        )
        admin.is_staff = True
        admin.is_superuser = True
        admin.first_name = 'Andrea'
        admin.last_name = 'Dela Fuente'
        admin.email = 'andrea.delafuente@gmail.com'
        if not admin.password or admin.password.startswith('!'):
            admin.set_password('admin123')
        admin.save()
        return admin

    def _ensure_competition(self, admin, reference):
        competition = None
        if reference:
            if str(reference).isdigit():
                competition = Competition.objects.filter(pk=int(reference)).first()
            if competition is None:
                competition = Competition.objects.filter(name=reference).first()
            if competition is None:
                raise SystemExit(self.style.ERROR(f'No competition matched "{reference}".'))
            competition.description = competition.description or COMPETITION_DESCRIPTION
            if competition.status == 'DRAFT':
                competition.status = 'ACTIVE'
            competition.save()
            return competition

        start = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=5)
        competition, created = Competition.objects.get_or_create(
            name=COMPETITION_NAME,
            defaults={
                'description': COMPETITION_DESCRIPTION,
                'start_date': start,
                'end_date': start + timedelta(days=11),
                'status': 'ACTIVE',
                'created_by': admin,
                'show_results': False,
            },
        )
        if created:
            self.stdout.write(f'Created competition "{competition.name}".')
        return competition

    def _create_sport_types(self):
        created = {}
        for name, team_based, description in SPORT_TYPES:
            sport, _ = SportType.objects.update_or_create(
                name=name,
                defaults={
                    'description': description,
                    'team_based': team_based,
                    'is_active': True,
                },
            )
            created[name] = sport
        return created

    def _create_venues(self):
        created = {}
        for name, location, capacity, description in VENUES:
            venue, _ = Venue.objects.update_or_create(
                name=name,
                defaults={
                    'location': location,
                    'capacity': capacity,
                    'description': description,
                    'is_active': True,
                },
            )
            created[name] = venue
        return created

    def _create_coaches(self):
        coaches = []
        for username, first, last, phone in COACHES:
            user, created = User.objects.get_or_create(
                username=username,
                defaults={'email': f'{username.replace("_", ".")}@jhcsc.edu.ph'},
            )
            if created or not user.password or user.password.startswith('!'):
                user.set_password('coach123')
            user.first_name = first
            user.last_name = last
            user.save()

            profile, _ = UserProfile.objects.get_or_create(user=user)
            if profile.role != UserProfile.Role.TEAM_MANAGER or profile.phone != phone:
                profile.role = UserProfile.Role.TEAM_MANAGER
                profile.phone = phone
                profile.save()
            coaches.append(user)
        return coaches

    def _create_teams(self, admin, coaches):
        teams = []
        for index, (name, colour, description) in enumerate(TEAMS):
            team, created = Team.objects.get_or_create(
                name=name,
                defaults={
                    'category': Team.Category.SPORTS,
                    'description': f'{description} Official {colour} colour.',
                    'status': Team.Status.APPROVED,
                    'created_by': admin,
                },
            )
            if not created:
                changed = []
                if team.status != Team.Status.APPROVED:
                    team.status = Team.Status.APPROVED
                    changed.append('status')
                if changed:
                    team.save(update_fields=changed + ['updated_at'])

            for number, member_name in enumerate(TEAM_MEMBERS[index], start=1):
                participant = self._ensure_member(index, number, member_name, team)
                TeamMembership.objects.update_or_create(
                    team=team,
                    participant=participant,
                    defaults={'member_number': number, 'status': TeamMembership.Status.ACTIVE},
                )

            TeamStaff.objects.get_or_create(
                team=team,
                user=coaches[index % len(coaches)],
                role=TeamStaff.Role.COACH,
            )
            teams.append(team)
        return teams

    def _ensure_member(self, team_index, number, member_name, team):
        email = f'team{team_index + 1:02d}.player{number}@jhcsc.edu.ph'
        participant, created = Participant.objects.get_or_create(
            email=email,
            defaults={
                'name': member_name,
                'phone': f'09{random.randint(10, 99)} 555 {random.randint(1000, 9999)}',
                'age': random.randint(17, 23),
                'gender': random.choice(['male', 'female']),
                'category': Participant.Category.OPEN,
                'team_name': team.name,
                'bio': f'{member_name.title()} plays for {team.name}.',
                'status': 'ACTIVE',
            },
        )
        if participant.team_name != team.name:
            participant.team_name = team.name
            participant.save(update_fields=['team_name'])
        return participant

    def _create_athletes(self, competition):
        """Create the individual athletes and return them in registration order."""
        athletes = []
        for index, (name, gender, age, bio) in enumerate(INDIVIDUAL_ATHLETES, start=1):
            email = f'athlete.sport{index:02d}@jhcsc.edu.ph'
            participant, _ = Participant.objects.get_or_create(
                email=email,
                defaults={
                    'name': name,
                    'phone': f'09{random.randint(10, 99)} 555 {random.randint(1000, 9999)}',
                    'age': age,
                    'gender': gender,
                    'category': Participant.Category.OPEN,
                    'bio': bio,
                    'status': 'ACTIVE',
                },
            )
            ParticipantCompetition.objects.get_or_create(
                competition=competition,
                participant=participant,
                defaults={'number': index},
            )
            athletes.append(participant)
        return athletes

    def _create_events(self, competition, sport_types, venues):
        events = []
        for spec in EVENT_SPECS:
            start_date = (competition.start_date + timedelta(days=spec.day_offset)).date()
            event, _ = SportsEvent.objects.update_or_create(
                competition=competition,
                name=spec.name,
                defaults={
                    'sport_type': sport_types[spec.sport],
                    'category': spec.category,
                    'gender': spec.gender,
                    'team_based': spec.team_based,
                    'format': spec.format,
                    'rules': spec.rules,
                    'max_teams': spec.max_teams,
                    'venue': venues[spec.venue],
                    'start_date': start_date,
                    'end_date': start_date + timedelta(days=spec.days - 1),
                    'status': SportsEvent.Status.SCHEDULED,
                },
            )
            event.spec = spec
            events.append(event)
        return events

    # ------------------------------------------------------------------
    # Brackets, schedule, and results
    # ------------------------------------------------------------------
    def _seed_event(self, event, board, athletes, log):
        spec = event.spec
        kind, wanted = spec.contestants
        if wanted == 0:
            log(f'  {event.name}: no bracket yet, entries stay open')
            return

        self._fill_entries(event, kind, wanted, athletes)
        if event.entries.filter(status=EventEntry.Status.CONFIRMED).count() < 2:
            log(f'  {event.name}: not enough confirmed entries, skipped')
            return

        event.matches.all().delete()
        generate_bracket(event)
        self._schedule_all(event, board)
        self._play_elapsed(event, board, log)
        self._sync_event_status(event)

    def _fill_entries(self, event, kind, wanted, athletes):
        if kind == 'teams':
            pool = Team.objects.filter(status=Team.Status.APPROVED).order_by('name')
            taken = set(event.entries.values_list('team_id', flat=True))
            for team in pool[:wanted]:
                if team.id not in taken:
                    EventEntry.objects.create(
                        event=event, team=team, status=EventEntry.Status.CONFIRMED,
                    )
            for team in pool[wanted:wanted + 1]:
                if team.id not in taken:
                    EventEntry.objects.create(event=event, team=team, status=EventEntry.Status.PENDING)
            return

        taken = set(event.entries.values_list('participant_id', flat=True))
        # Honour a gendered division so the women's event fields women.
        gender = event.spec.gender
        pool = list(athletes)
        if gender in ('male', 'female'):
            matching = [p for p in pool if p.gender == gender]
            if len(matching) >= wanted:
                pool = matching
        for participant in pool[:wanted]:
            if participant.id not in taken:
                EventEntry.objects.create(
                    event=event, participant=participant, status=EventEntry.Status.CONFIRMED,
                )

    def _event_window(self, event):
        """The playable window for an event, defaulting to the competition dates."""
        if event.start_date:
            start = timezone.make_aware(datetime.combine(event.start_date, time(8, 0)))
        else:
            start = event.competition.start_date
        if event.end_date:
            end = timezone.make_aware(datetime.combine(event.end_date, time(18, 0)))
        else:
            end = event.competition.end_date
        return start, end

    def _ordered_matches(self, event):
        """Round 1 first, then each later round, so winners advance in order."""
        by_round = OrderedDict()
        for match in event.matches.all().order_by('round_number', 'id'):
            by_round.setdefault(match.round_number, []).append(match)
        ordered = []
        for round_number in sorted(by_round):
            ordered.extend(by_round[round_number])
        return ordered

    def _schedule_all(self, event, board):
        spec = event.spec
        window_start, window_end = self._event_window(event)
        cursor = window_start

        for match in self._ordered_matches(event):
            if match.scheduled_start and match.scheduled_end and match.venue_id:
                cursor = max(cursor, match.scheduled_end)
                continue
            booked = board.book(
                earliest=cursor,
                duration=spec.duration,
                deadline=window_end,
                turnaround=spec.turnaround,
                preferred_id=event.venue_id,
            )
            if booked is None:
                self.stdout.write(self.style.WARNING(
                    f'  No free slot left for {event.name} - {match.label}'
                ))
                continue
            start, end, venue = booked
            match.venue = venue
            match.scheduled_start = start
            match.scheduled_end = end
            if event.venue_id and venue.id != event.venue_id and not match.notes:
                match.notes = f'Moved off {event.venue.name} to clear the schedule.'
            match.save(update_fields=['venue', 'scheduled_start', 'scheduled_end', 'notes', 'updated_at'])
            cursor = max(cursor, end)

    def _play_elapsed(self, event, board, log):
        """Record results for every match whose slot has already passed."""
        spec = event.spec
        now = timezone.now()
        played = 0

        # Completing every group match reveals a knockout stage, so repeat until
        # no further round becomes available.
        for _ in range(4):
            progressed = False
            for match in self._ordered_matches(event):
                if match.status == Match.Status.COMPLETED:
                    continue
                if match.scheduled_start is None or match.scheduled_start >= now:
                    continue
                if match.entries.count() != 2:
                    continue
                try:
                    record_match_result(match, self._scores(spec), notes=random.choice(MATCH_NOTES))
                except ValueError:
                    continue
                played += 1
                progressed = True
            if not progressed:
                break
            if event.matches.filter(scheduled_start__isnull=True).exists():
                self._schedule_all(event, board)

        if played:
            log(f'  {event.name}: {played} result(s) recorded')

    def _scores(self, spec):
        winner = random.uniform(*spec.win_scores)
        loser = random.uniform(*spec.lose_scores)
        if winner <= loser:
            winner = loser + 1
        return {1: loser, 2: winner} if random.random() < 0.5 else {1: winner, 2: loser}

    def _sync_event_status(self, event):
        total = event.matches.count()
        completed = event.matches.filter(status=Match.Status.COMPLETED).count()
        if total and completed == total:
            status = SportsEvent.Status.COMPLETED
        elif completed:
            status = SportsEvent.Status.ONGOING
        elif event.start_date and event.start_date <= timezone.now().date():
            status = SportsEvent.Status.ONGOING
        else:
            status = SportsEvent.Status.SCHEDULED
        if event.status != status:
            event.status = status
            event.save(update_fields=['status', 'updated_at'])

    def _sync_competition(self, competition):
        events = list(competition.sport_events.all())
        if not events:
            return

        completed = sum(1 for event in events if event.status == SportsEvent.Status.COMPLETED)
        if completed == len(events):
            status, show_results = 'COMPLETED', True
        elif any(event.status in (SportsEvent.Status.ONGOING, SportsEvent.Status.COMPLETED)
                 for event in events):
            status, show_results = 'ACTIVE', False
        elif competition.end_date and competition.end_date < timezone.now():
            status, show_results = 'COMPLETED', True
        else:
            status = competition.status if competition.status != 'DRAFT' else 'ACTIVE'
            show_results = competition.show_results

        if competition.status != status or competition.show_results != show_results:
            competition.status = status
            competition.show_results = show_results
            competition.save(update_fields=['status', 'show_results', 'updated_at'])
