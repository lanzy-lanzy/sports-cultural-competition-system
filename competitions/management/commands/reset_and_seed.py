"""Reset the competition database and seed the baseline competitions.

Wipes every transactional row - competitions, rounds, criteria, participants,
teams, sport types, venues, sport events, matches, scores, awards,
registrations, eligibility records, protests, announcements, notifications and
activity logs - then rebuilds the starting point of a fresh season:

* four Socio Cultural competitions (singing, dance, essay writing, quiz bee)
  with their rounds and judging criteria, and
* one Basketball and one Volleyball competition, each with its sport type,
  home venue, and an empty event shell.

Admin and judge accounts are never touched: superusers and anyone carrying the
Administrator or Judge role (plus their UserProfile and Judge rows) survive the
reset, and the seeded competitions are created under the preserved admin.

No teams and no participants are seeded, so every competition starts empty and
ready for registration.

Run it with::

    .venv\\Scripts\\python.exe manage.py reset_and_seed

Useful flags::

    --dry-run    report what would be removed and seeded, change nothing
    --yes        skip the confirmation prompt
"""

import sys
from datetime import timedelta
from decimal import Decimal

from django.contrib.admin.models import LogEntry
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction
from django.db.models import Q
from django.utils import timezone

from accounts.models import UserProfile
from announcements.models import Announcement, Notification
from audit.models import AuditLog
from competitions.models import Competition, Criterion, Round
from eligibility.models import EligibilityRecord
from judges.models import Judge, JudgeAssignment
from participants.models import Participant, ParticipantCompetition
from protests.models import Protest
from registrations.models import EventRegistration, RegistrationTemplate
from scoring.models import Award, AwardRecipient, CompetitionResult, Score, ScoreChangeLog
from sms.models import SmsMessage
from sports.models import EventEntry, Match, MatchEntry, SportsEvent, SportType, Venue
from teams.models import Team, TeamMembership, TeamStaff

SPORT_COMPETITIONS = [
    {
        'name': 'JHCSC INTRAMURAL BASKETBALL 2026',
        'description': (
            'Intramural basketball championship of J.H. Cerilles State College. '
            'Approved teams register through the sports coordinator, then the '
            'bracket is generated and match results are recorded per game.'
        ),
        'days_ahead': 14,
        'length_days': 8,
        'sport': {
            'name': 'Basketball',
            'description': 'Five-a-side court sport played with a size 7 ball.',
        },
        'venue': {
            'name': 'Main Gymnasium',
            'location': 'Main Campus, North Wing',
            'capacity': 1500,
            'description': 'Indoor basketball court with retractable bleachers.',
        },
        'event': {
            'name': 'Basketball - Open',
            'gender': 'open',
            'format': SportsEvent.Format.SINGLE_ELIMINATION,
            'max_teams': 8,
            'rules': (
                'FIBA rules. Four 10-minute quarters, a 2 minute break between '
                'quarters and a 15 minute half time. A 5 minute overtime is '
                'played if tied at the end of regulation.'
            ),
        },
    },
    {
        'name': 'JHCSC INTRAMURAL VOLLEYBALL 2026',
        'description': (
            'Intramural volleyball championship of J.H. Cerilles State College. '
            'Approved teams are drawn into groups before the knockout stage is '
            'seeded from the group standings.'
        ),
        'days_ahead': 14,
        'length_days': 8,
        'sport': {
            'name': 'Volleyball',
            'description': 'Indoor court sport, best of three sets to 25 points.',
        },
        'venue': {
            'name': 'Covered Court',
            'location': 'Engineering Building, Ground Floor',
            'capacity': 800,
            'description': 'Covered multi-purpose court used for volleyball.',
        },
        'event': {
            'name': 'Volleyball - Open',
            'gender': 'open',
            'format': SportsEvent.Format.GROUP_STAGE,
            'max_teams': 12,
            'rules': (
                'Best of three sets to 25 points, deciding set to 15. Rally '
                'scoring with a technical timeout at 8 points in the first two '
                'sets.'
            ),
        },
    },
]

CULTURAL_COMPETITIONS = [
    {
        'name': 'HIMIG NG BAYAN 2026: SOLO SINGING COMPETITION',
        'description': (
            'Search for the college\u2019s best solo voice. Contestants perform '
            'one number in the preliminary round and return for the finals, where '
            'the panel decides the champion.'
        ),
        'cultural_event_type': Competition.CulturalEventType.SINGING,
        'day_offset': 0,
        'rounds': [
            {
                'name': 'PRELIMINARY ROUND',
                'description': 'Each contestant performs one song of their choice before the panel.',
                'weight': Decimal('40.00'),
                'criteria': [
                    ('VOCAL QUALITY & TONE', 'Pitch accuracy, tone color, and control of the voice.', Decimal('40.00')),
                    ('SONG INTERPRETATION', 'Understanding and expression of the song\u2019s meaning.', Decimal('30.00')),
                    ('STAGE PRESENCE', 'Confidence, poise, and connection with the audience.', Decimal('30.00')),
                ],
            },
            {
                'name': 'FINALS ROUND',
                'description': 'Finalists perform an OPM classic with live accompaniment.',
                'weight': Decimal('60.00'),
                'criteria': [
                    ('VOCAL TECHNIQUE & CONTROL', 'Breath support, dynamics, and technical proficiency.', Decimal('35.00')),
                    ('EMOTIONAL DELIVERY', 'Ability to convey emotion and tell a story through song.', Decimal('35.00')),
                    ('AUDIENCE ENGAGEMENT', 'Energy, rapport, and ability to hold the audience.', Decimal('30.00')),
                ],
            },
        ],
    },
    {
        'name': 'LATIN AMERICAN DANCE SPORT 2026',
        'description': (
            'Solo and pair dance competition covering the Latin American routines. '
            'The panel scores technical merit and performance across the '
            'preliminary round and the finals.'
        ),
        'cultural_event_type': Competition.CulturalEventType.DANCE,
        'day_offset': 1,
        'rounds': [
            {
                'name': 'PRELIMINARY ROUND',
                'description': 'Groups perform their opening routine for qualification.',
                'weight': Decimal('40.00'),
                'criteria': [
                    ('TECHNIQUE & EXECUTION', 'Body line, footwork, and posture in the required steps.', Decimal('40.00')),
                    ('CHOREOGRAPHY & CREATIVITY', 'Originality of the routine and use of space.', Decimal('30.00')),
                    ('MUSICALITY & TIMING', 'Accents and phrasing held against the music.', Decimal('30.00')),
                ],
            },
            {
                'name': 'FINALS ROUND',
                'description': 'Qualifying pairs perform their championship routine.',
                'weight': Decimal('60.00'),
                'criteria': [
                    ('TECHNICAL MERIT', 'Difficulty and cleanliness of the executed figures.', Decimal('35.00')),
                    ('PERFORMANCE & SHOWMANSHIP', 'Projection, expression, and stage command.', Decimal('35.00')),
                    ('COSTUMING & STAGING', 'Appropriateness of attire and transition management.', Decimal('30.00')),
                ],
            },
        ],
    },
    {
        'name': 'SULAT AT SALITA 2026: ESSAY WRITING COMPETITION',
        'description': (
            'On-the-spot essay writing competition held in the academic building. '
            'Entrants receive the topic at the start of the session and submit a '
            'single finished piece for the panel.'
        ),
        'cultural_event_type': Competition.CulturalEventType.ESSAY_WRITING,
        'day_offset': 2,
        'rounds': [
            {
                'name': 'FINAL ROUND',
                'description': 'Two-hour on-the-spot writing of the submitted essay.',
                'weight': Decimal('100.00'),
                'criteria': [
                    ('CONTENT & RELEVANCE', 'Depth of ideas and how well the topic is answered.', Decimal('40.00')),
                    ('ORGANIZATION & COHERENCE', 'Structure, flow, and unity of paragraphs.', Decimal('30.00')),
                    ('GRAMMAR & STYLE', 'Correctness of language and quality of expression.', Decimal('30.00')),
                ],
            },
        ],
    },
    {
        'name': 'BAYANIHAN QUIZ BEE 2026',
        'description': (
            'Inter-college quiz bee covering general information, current events, '
            'and college history. Delegations answer the easy, average, and '
            'difficult rounds before the clincher round decides the title.'
        ),
        'cultural_event_type': Competition.CulturalEventType.QUIZ_BEE,
        'day_offset': 3,
        'rounds': [
            {
                'name': 'FINAL ROUND',
                'description': 'Single session with the easy, average, difficult, and clincher sets.',
                'weight': Decimal('100.00'),
                'criteria': [
                    ('EASY ROUND', 'Twenty point questions answered within thirty seconds.', Decimal('20.00')),
                    ('AVERAGE ROUND', 'Thirty point questions answered within forty-five seconds.', Decimal('30.00')),
                    ('DIFFICULT ROUND', 'Thirty point questions answered within sixty seconds.', Decimal('30.00')),
                    ('CLINCHER ROUND', 'Sudden death set used to break an outright tie.', Decimal('20.00')),
                ],
            },
        ],
    },
]

# Tables re-seeded by this command. Their counters are reset so a fresh season
# starts at id 1 again; account tables are deliberately left alone.
SEQUENCE_TABLES = (Competition, Round, Criterion, SportType, Venue, SportsEvent)


class Command(BaseCommand):
    help = 'Resets all competition data (keeping admin and judge accounts) and seeds the base competitions.'

    def add_arguments(self, parser):
        parser.add_argument('--yes', action='store_true',
                            help='Skip the confirmation prompt.')
        parser.add_argument('--dry-run', action='store_true',
                            help='Report what would be removed and seeded without changing data.')

    def handle(self, *args, **options):
        preserved = self._preserved_user_ids()
        admin = self._seed_admin(preserved)

        if options['dry_run']:
            self._report(preserved, admin)
            return

        if not options['yes']:
            self._confirm(preserved, admin)

        # The wipe and the seed are separate transactions: MySQL commits
        # implicitly when the primary key counters are reset between them, so
        # one atomic block could not cover all three steps. If the seed fails,
        # re-running the command wipes again and rebuilds from scratch.
        with transaction.atomic():
            removed = self._wipe(preserved)

        self._reset_sequences()

        with transaction.atomic():
            seeded = self._seed(admin)

        self._clear_sessions()
        self.stdout.write(self.style.SUCCESS(
            f'Reset complete. Removed {removed:,} row(s) of competition data; '
            f'seeded {seeded["competitions"]} competitions.'
        ))
        self._report_seed(admin=admin, seeded=seeded, preserved=preserved)

    # ------------------------------------------------------------------
    # Account protection
    # ------------------------------------------------------------------
    def _preserved_user_ids(self):
        """Admin and judge accounts are never part of the reset."""
        managers = User.objects.filter(Q(is_superuser=True) | Q(is_staff=True)).values_list('id', flat=True)
        judged = Judge.objects.values_list('user_id', flat=True)
        role_kept = UserProfile.objects.filter(
            role__in=(UserProfile.Role.ADMINISTRATOR, UserProfile.Role.JUDGE),
        ).values_list('user_id', flat=True)
        return set(managers) | set(judged) | set(role_kept)

    def _seed_admin(self, preserved):
        """The preserved admin account that owns the seeded competitions."""
        admin = User.objects.filter(pk__in=preserved, is_superuser=True).order_by('id').first()
        if admin is None:
            admin = User.objects.filter(
                pk__in=preserved,
                account_profile__role=UserProfile.Role.ADMINISTRATOR,
            ).order_by('id').first()
        if admin is None:
            raise CommandError(
                'No admin account found to own the seeded competitions. '
                'Create one with "manage.py createsuperuser" first.'
            )
        return admin

    # ------------------------------------------------------------------
    # Reset
    # ------------------------------------------------------------------
    def _wipe(self, preserved):
        """Delete every transactional row except the preserved accounts."""
        # Keep the profile of anyone who is both a judge/admin and a registered
        # participant; their account data must survive. NULL user rows are not
        # matched by the negated subquery, so they need the explicit branch.
        participants = Participant.objects.filter(
            Q(user__isnull=True) | ~Q(user__in=preserved)
        )

        steps = (
            ('score change logs', ScoreChangeLog.objects.all()),
            ('scores', Score.objects.all()),
            ('competition results', CompetitionResult.objects.all()),
            ('award recipients', AwardRecipient.objects.all()),
            ('awards', Award.objects.all()),
            ('match entries', MatchEntry.objects.all()),
            ('matches', Match.objects.all()),
            ('event entries', EventEntry.objects.all()),
            ('sport events', SportsEvent.objects.all()),
            ('venues', Venue.objects.all()),
            ('sport types', SportType.objects.all()),
            ('registration templates', RegistrationTemplate.objects.all()),
            ('registrations', EventRegistration.objects.all()),
            ('eligibility records', EligibilityRecord.objects.all()),
            ('protests', Protest.objects.all()),
            ('notifications', Notification.objects.all()),
            ('announcements', Announcement.objects.all()),
            ('sms messages', SmsMessage.objects.all()),
            ('participant entries', ParticipantCompetition.objects.all()),
            ('participants', participants),
            ('team memberships', TeamMembership.objects.all()),
            ('team staff', TeamStaff.objects.all()),
            ('teams', Team.objects.all()),
            ('judge assignments', JudgeAssignment.objects.all()),
            ('criteria', Criterion.objects.all()),
            ('rounds', Round.objects.all()),
            ('competitions', Competition.objects.all()),
            ('audit logs', AuditLog.objects.all()),
            ('admin log entries', LogEntry.objects.all()),
        )

        removed = 0
        for label, queryset in steps:
            count = queryset.count()
            if count:
                queryset.delete()
                removed += count
                self.stdout.write(f'  cleared {label}: {count}')

        # Every account that is neither an admin nor a judge goes, together
        # with the rows that cascade from it (profiles, preferences, teams).
        stale_users = User.objects.exclude(pk__in=preserved)
        count = stale_users.count()
        if count:
            stale_users.delete()
            removed += count
            self.stdout.write(f'  cleared non-admin/non-judge accounts: {count}')

        return removed

    def _clear_sessions(self):
        """Drop login sessions so stale cookies cannot outlive the reset."""
        from django.core.management import call_command
        call_command('clearsessions')

    def _reset_sequences(self):
        """Restart the primary key counters of the re-seeded tables."""
        if connection.vendor != 'mysql':
            return
        with connection.cursor() as cursor:
            for model in SEQUENCE_TABLES:
                cursor.execute(f'ALTER TABLE `{model._meta.db_table}` AUTO_INCREMENT = 1')

    # ------------------------------------------------------------------
    # Seed
    # ------------------------------------------------------------------
    def _seed(self, admin):
        opened_at = timezone.now().replace(hour=8, minute=0, second=0, microsecond=0)
        created = {'competitions': 0, 'rounds': 0, 'criteria': 0, 'events': 0}

        for spec in SPORT_COMPETITIONS:
            start = opened_at + timedelta(days=spec['days_ahead'])
            end = start + timedelta(days=spec['length_days'])
            competition = Competition.objects.create(
                name=spec['name'],
                description=spec['description'],
                kind=Competition.Kind.SPORTS,
                gold_points=Decimal('10.00'),
                silver_points=Decimal('5.00'),
                bronze_points=Decimal('3.00'),
                start_date=start,
                end_date=end,
                status='ACTIVE',
                created_by=admin,
                show_results=False,
            )
            created['competitions'] += 1

            sport = SportType.objects.create(
                name=spec['sport']['name'],
                description=spec['sport']['description'],
                team_based=True,
                is_active=True,
            )
            venue = Venue.objects.create(
                name=spec['venue']['name'],
                location=spec['venue']['location'],
                capacity=spec['venue']['capacity'],
                description=spec['venue']['description'],
                is_active=True,
            )
            event_spec = spec['event']
            SportsEvent.objects.create(
                competition=competition,
                sport_type=sport,
                name=event_spec['name'],
                category=SportsEvent.Category.OPEN_CATEGORY,
                gender=event_spec['gender'],
                team_based=True,
                format=event_spec['format'],
                rules=event_spec['rules'],
                max_teams=event_spec['max_teams'],
                venue=venue,
                start_date=start.date(),
                end_date=end.date(),
                status=SportsEvent.Status.PLANNED,
            )
            created['events'] += 1

        for spec in CULTURAL_COMPETITIONS:
            start = opened_at + timedelta(days=7 + spec['day_offset'])
            end = start + timedelta(hours=9)
            competition = Competition.objects.create(
                name=spec['name'],
                description=spec['description'],
                kind=Competition.Kind.CULTURAL,
                cultural_event_type=spec['cultural_event_type'],
                gold_points=Decimal('10.00'),
                silver_points=Decimal('5.00'),
                bronze_points=Decimal('3.00'),
                start_date=start,
                end_date=end,
                status='ACTIVE',
                created_by=admin,
                show_results=False,
            )
            created['competitions'] += 1

            for order, round_spec in enumerate(spec['rounds'], start=1):
                round_obj = Round.objects.create(
                    competition=competition,
                    name=round_spec['name'],
                    description=round_spec['description'],
                    order=order,
                    status='PENDING',
                    weight_percentage=round_spec['weight'],
                )
                created['rounds'] += 1
                for name, description, max_score in round_spec['criteria']:
                    Criterion.objects.create(
                        round=round_obj,
                        name=name,
                        description=description,
                        max_score=max_score,
                        weight_percentage=Decimal('0.00'),
                    )
                    created['criteria'] += 1

        return created

    # ------------------------------------------------------------------
    # Reporting
    # ------------------------------------------------------------------
    def _preserved_accounts(self, preserved):
        return User.objects.filter(pk__in=preserved).order_by('id').select_related('account_profile')

    def _describe_account(self, user):
        profile = getattr(user, 'account_profile', None)
        if profile:
            return f'{user.username} ({profile.get_role_display()})'
        return f'{user.username} (superuser)'

    def _confirm(self, preserved, admin):
        kept = ', '.join(self._describe_account(user) for user in self._preserved_accounts(preserved))
        self.stdout.write(self.style.WARNING(
            'This wipes all competition data and re-seeds the base competitions.\n'
            f'Kept accounts: {kept or "none"}.\n'
            f'Competitions will be created under "{admin.username}".'
        ))
        if not sys.stdin.isatty():
            raise CommandError('Run non-interactively with --yes once you have reviewed --dry-run.')
        answer = input('Type "yes" to continue: ').strip().lower()
        if answer != 'yes':
            raise CommandError('Aborted. Nothing was changed.')

    def _report(self, preserved, admin):
        self.stdout.write(self.style.WARNING('DRY RUN - no data was changed.\n'))
        self.stdout.write('Accounts that would be kept:')
        for user in self._preserved_accounts(preserved):
            self.stdout.write(f'  {user.id:>3} {self._describe_account(user)}')

        stale = User.objects.exclude(pk__in=preserved).count()
        self.stdout.write(f'\nNon-admin/non-judge accounts that would be removed: {stale}')
        self.stdout.write(self.style.SUCCESS(
            f'\nWould seed {len(SPORT_COMPETITIONS)} sports competitions '
            f'(basketball, volleyball) and {len(CULTURAL_COMPETITIONS)} socio cultural competitions '
            f'under "{admin.username}".'
        ))

    def _report_seed(self, admin, seeded, preserved):
        self.stdout.write('\nSeeded competitions:')
        for competition in Competition.objects.select_related('created_by').order_by('kind', 'id'):
            if competition.kind == Competition.Kind.CULTURAL:
                detail = competition.get_cultural_event_type_display()
                kind = 'SOCIO CULTURAL'
            else:
                event = competition.sport_events.first()
                detail = event.sport_type.name if event else 'no event yet'
                kind = 'SPORTS'
            self.stdout.write(
                f'  [{kind}] {competition.name} ({detail}) - '
                f'{competition.rounds.count()} round(s), '
                f'{competition.sport_events.count()} event(s), '
                f'{competition.participants.count()} participant(s)'
            )

        self.stdout.write(
            f'\nTotals: {seeded["competitions"]} competitions, {seeded["rounds"]} rounds, '
            f'{seeded["criteria"]} criteria, {seeded["events"]} sport events.'
        )
        self.stdout.write('No teams and no participants were created.')
        kept = ', '.join(user.username for user in self._preserved_accounts(preserved))
        self.stdout.write(f'Preserved accounts: {kept or "none"}.')
        self.stdout.write(
            'Judge panels were cleared with their competitions - re-assign them to the new '
            f'rounds from the management pages. Owner used for the seed: "{admin.username}".'
        )
