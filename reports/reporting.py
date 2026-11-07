"""Structured report definitions shared by CSV, PDF, and print outputs.

Every report is described once as a :class:`ReportData` value. The PDF builder
and the printable HTML template render the same sections, so an exported
document always matches what is shown on screen.
"""

from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from django.utils import timezone

from competitions.models import Competition
from participants.models import Participant
from registrations.models import EventRegistration
from sports.models import Match
from teams.models import Team


@dataclass
class ReportSection:
    """One table within a report."""

    columns: list[str]
    rows: list[list[str]]
    title: str = ''
    numeric_columns: tuple[int, ...] = ()
    empty_message: str = 'No records are available for this section.'


@dataclass
class ReportData:
    """A complete, render-ready report."""

    key: str
    title: str
    subtitle: str
    sections: list[ReportSection]
    summary: list[tuple[str, str]] = field(default_factory=list)
    competition: Competition | None = None
    filename: str = ''
    generated_at: datetime = field(default_factory=timezone.now)

    @property
    def record_count(self) -> int:
        return sum(len(section.rows) for section in self.sections)


def _text(value) -> str:
    """Convert a model value into safe display text."""
    if value is None:
        return ''
    if isinstance(value, datetime):
        if timezone.is_aware(value):
            value = timezone.localtime(value)
        return value.strftime('%b %d, %Y %I:%M %p')
    if isinstance(value, date):
        return value.strftime('%b %d, %Y')
    if isinstance(value, Decimal):
        return _number(value)
    return str(value)


def _number(value) -> str:
    """Format decimals without noisy trailing zeroes."""
    if value is None or value == '':
        return ''
    try:
        number = Decimal(value)
    except (InvalidOperation, TypeError, ValueError):
        return str(value)
    text = f'{number:f}'
    if '.' in text:
        text = text.rstrip('0').rstrip('.')
    return text


def _competition_kind(competition: Competition) -> str:
    if competition.kind == Competition.Kind.CULTURAL:
        return 'Socio Cultural'
    return competition.get_kind_display()


def _competition_window(competition: Competition) -> str:
    start = _text(competition.start_date)
    end = _text(competition.end_date)
    return f'{start} - {end}' if start and end else start or end


def _user_name(user) -> str:
    if not user:
        return ''
    return user.get_full_name() or user.username


def participants_report() -> ReportData:
    participants = Participant.objects.order_by('name')
    rows = []
    active = 0
    teams = set()
    for participant in participants:
        if participant.status == 'ACTIVE':
            active += 1
        if participant.team_name:
            teams.add(participant.team_name)
        rows.append([
            participant.participant_id,
            participant.name,
            participant.phone,
            _number(participant.age),
            participant.get_category_display(),
            participant.get_gender_display(),
            participant.get_status_display(),
            participant.team_name,
            _text(participant.registration_date),
        ])
    return ReportData(
        key='participants',
        title='Participant Register',
        subtitle=(
            'Consolidated register of all participants recognised by the '
            'competition management office.'
        ),
        sections=[ReportSection(
            title='Participant register',
            columns=[
                'Participant ID', 'Name', 'Phone', 'Age', 'Category', 'Gender',
                'Status', 'Team / Delegation', 'Registered',
            ],
            rows=rows,
            numeric_columns=(3,),
            empty_message='No participants have been registered yet.',
        )],
        summary=[
            ('Total participants', str(len(rows))),
            ('Active participants', str(active)),
            ('Teams represented', str(len(teams))),
        ],
        filename='participant-register',
    )


def team_rosters_report() -> ReportData:
    teams = Team.objects.order_by('name').prefetch_related(
        'memberships__participant', 'staff_assignments__user',
    )
    rows = []
    members = 0
    approved = 0
    for team in teams:
        if team.status == Team.Status.APPROVED:
            approved += 1
        staff_names = '; '.join(
            _user_name(assignment.user) for assignment in team.staff_assignments.all()
        )
        memberships = list(team.memberships.all())
        if not memberships:
            rows.append([
                team.code, team.name, team.get_category_display(),
                team.get_status_display(), '', '', '', staff_names,
            ])
            continue
        for membership in memberships:
            members += 1
            rows.append([
                team.code,
                team.name,
                team.get_category_display(),
                team.get_status_display(),
                _number(membership.member_number),
                membership.participant.name,
                membership.get_status_display(),
                staff_names,
            ])
    return ReportData(
        key='rosters',
        title='Team & Delegation Rosters',
        subtitle=(
            'Official membership and coaching staff listing for every team and '
            'delegation in the competition programme.'
        ),
        sections=[ReportSection(
            title='Team and delegation roster',
            columns=[
                'Team Code', 'Team / Delegation', 'Category', 'Status',
                'Member No.', 'Member Name', 'Member Status', 'Coaching Staff',
            ],
            rows=rows,
            numeric_columns=(4,),
            empty_message='No teams or delegations have been created yet.',
        )],
        summary=[
            ('Teams & delegations', str(len(teams))),
            ('Approved teams', str(approved)),
            ('Members listed', str(members)),
        ],
        filename='team-rosters',
    )


def registrations_report() -> ReportData:
    registrations = EventRegistration.objects.select_related(
        'registrant', 'team', 'participant', 'competition', 'sport_event', 'reviewed_by',
    ).order_by('-created_at')
    rows = []
    status_counts = {
        EventRegistration.Status.PENDING: 0,
        EventRegistration.Status.UNDER_REVIEW: 0,
        EventRegistration.Status.APPROVED: 0,
        EventRegistration.Status.REJECTED: 0,
    }
    for registration in registrations:
        if registration.status in status_counts:
            status_counts[registration.status] += 1
        rows.append([
            _user_name(registration.registrant),
            registration.contestant_name,
            registration.target_name,
            'Sport event' if registration.sport_event_id else 'Competition',
            registration.team.name if registration.team else '',
            registration.get_status_display(),
            _text(registration.created_at),
            _user_name(registration.reviewed_by),
            _text(registration.reviewed_at),
        ])
    return ReportData(
        key='registrations',
        title='Event Registration Register',
        subtitle=(
            'Record of online registrations, approvals, and review decisions.'
        ),
        sections=[ReportSection(
            title='Registration entries',
            columns=[
                'Registrant', 'Contestant', 'Target', 'Type', 'Team', 'Status',
                'Submitted', 'Reviewed By', 'Reviewed At',
            ],
            rows=rows,
            empty_message='No event registrations have been submitted yet.',
        )],
        summary=[
            ('Total registrations', str(len(rows))),
            ('Pending', str(status_counts[EventRegistration.Status.PENDING])),
            ('Approved', str(status_counts[EventRegistration.Status.APPROVED])),
            ('Rejected', str(status_counts[EventRegistration.Status.REJECTED])),
        ],
        filename='event-registrations',
    )


def schedule_report() -> ReportData:
    matches = Match.objects.select_related(
        'event__competition', 'event__sport_type', 'venue',
    ).order_by('event__competition__name', 'event__name', 'scheduled_start', 'id')
    rows = []
    completed = 0
    scheduled = 0
    venues = set()
    for match in matches:
        if match.status == Match.Status.COMPLETED:
            completed += 1
        if match.status == Match.Status.SCHEDULED:
            scheduled += 1
        if match.venue:
            venues.add(match.venue.name)
        rows.append([
            match.event.competition.name,
            match.event.name,
            match.label,
            _number(match.round_number),
            match.contestants_display(),
            match.venue.name if match.venue else '',
            _text(match.scheduled_start),
            _text(match.scheduled_end),
            match.get_status_display(),
        ])
    return ReportData(
        key='schedule',
        title='Official Match Schedule',
        subtitle=(
            'Consolidated timetable of fixtures, venues, contestants, and match '
            'status across all competitions.'
        ),
        sections=[ReportSection(
            title='Match schedule',
            columns=[
                'Competition', 'Sport Event', 'Match', 'Round', 'Contestants',
                'Venue', 'Start', 'End', 'Status',
            ],
            rows=rows,
            numeric_columns=(3,),
            empty_message='No matches have been scheduled yet.',
        )],
        summary=[
            ('Total matches', str(len(rows))),
            ('Completed', str(completed)),
            ('Still scheduled', str(scheduled)),
            ('Venues used', str(len(venues))),
        ],
        filename='match-schedule',
    )


def medal_tally_report(category: str = '') -> ReportData:
    from scoring.services import compute_overall_medal_tally

    competitions = Competition.objects.all()
    category_label = 'All competitions'
    if category == 'cultural':
        competitions = competitions.filter(kind=Competition.Kind.CULTURAL)
        category_label = 'Socio-cultural competitions'
    elif category == 'sports':
        competitions = competitions.exclude(kind=Competition.Kind.CULTURAL)
        category_label = 'Sports competitions'

    overall = compute_overall_medal_tally(competitions)
    columns = [
        'Rank', 'Team / Delegation', 'Status', 'W', 'L', 'D',
        'Gold', 'Silver', 'Bronze', 'Points',
    ]
    numeric = (0, 3, 4, 5, 6, 7, 8, 9)

    def rows_for(source_rows):
        return [[
            _number(row['rank']),
            row['name'],
            row.get('status_display', ''),
            _number(row.get('wins', '')),
            _number(row.get('losses', '')),
            _number(row.get('draws', '')),
            _number(row['gold']),
            _number(row['silver']),
            _number(row['bronze']),
            _number(row['points']),
        ] for row in source_rows]

    sections = [ReportSection(
        title='Overall medal standings',
        columns=columns,
        rows=rows_for(overall['rows']),
        numeric_columns=numeric,
        empty_message='No medals have been awarded yet.',
    )]
    for entry in overall['breakdown']:
        if not entry['rows']:
            continue
        sections.append(ReportSection(
            title=f"{entry['competition'].name} · {_competition_kind(entry['competition'])}",
            columns=columns,
            rows=rows_for(entry['rows']),
            numeric_columns=numeric,
            empty_message='No medals have been awarded for this competition.',
        ))

    totals = overall['totals']
    return ReportData(
        key='medal-tally',
        title='Medal Tally & Delegation Standings',
        subtitle=(
            'Official medal count and delegation ranking derived from sport '
            'podiums, judged results, and recorded awards.'
        ),
        sections=sections,
        summary=[
            ('Filter', category_label),
            ('Gold medals', _number(totals['gold'])),
            ('Silver medals', _number(totals['silver'])),
            ('Bronze medals', _number(totals['bronze'])),
        ],
        filename='medal-tally',
    )


def judge_scores_report(competition: Competition) -> ReportData:
    from scoring.models import Score

    scores = Score.objects.filter(
        criterion__round__competition=competition,
    ).select_related(
        'criterion__round', 'judge__user', 'participant',
    ).order_by(
        'criterion__round__order', 'criterion__name', 'participant__name', 'judge_id',
    )
    rows = []
    judges = set()
    rounds = set()
    for score in scores:
        judges.add(score.judge_id)
        rounds.add(score.criterion.round_id)
        rows.append([
            score.criterion.round.name,
            score.criterion.name,
            _number(score.criterion.max_score),
            _user_name(score.judge.user if score.judge else None),
            score.participant.name,
            _number(score.score),
            score.get_status_display(),
            score.remarks,
            _text(score.timestamp),
        ])
    return ReportData(
        key='judge-scores',
        title='Judge Score Sheet',
        subtitle=(
            'Detailed scoring record submitted by the judging panel for this '
            'competition.'
        ),
        sections=[ReportSection(
            title='Score entries',
            columns=[
                'Round', 'Criterion', 'Max', 'Judge', 'Participant', 'Score',
                'Status', 'Remarks', 'Scored At',
            ],
            rows=rows,
            numeric_columns=(2, 5),
            empty_message='No scores have been recorded for this competition.',
        )],
        summary=[
            ('Rounds scored', str(len(rounds))),
            ('Judges recorded', str(len(judges))),
            ('Score entries', str(len(rows))),
        ],
        competition=competition,
        filename=f'judge-score-sheet-{competition.id}',
    )


def standings_report(competition: Competition) -> ReportData:
    from scoring.models import CompetitionResult
    from scoring.services import build_overall_standings

    standings = build_overall_standings(competition)
    participant_lookup = {p.id: p.name for p in competition.participants.all()}
    final_rows = [
        [
            _number(data['rank']),
            participant_lookup.get(participant_id, f'#{participant_id}'),
            _number(data['total']),
        ]
        for participant_id, data in sorted(standings.items(), key=lambda item: item[1]['rank'])
    ]
    sections = [ReportSection(
        title='Final weighted standings',
        columns=['Rank', 'Participant', 'Score'],
        rows=final_rows,
        numeric_columns=(0, 2),
        empty_message='No final standings have been computed for this competition.',
    )]

    rounds = list(competition.rounds.order_by('order'))
    for round_obj in rounds:
        results = CompetitionResult.objects.filter(
            round=round_obj,
        ).select_related('participant').order_by('rank')
        sections.append(ReportSection(
            title=f"Round {round_obj.order}: {round_obj.name}",
            columns=['Rank', 'Participant', 'Score'],
            rows=[
                [
                    _number(result.rank),
                    result.participant.name,
                    _number(result.total_score),
                ]
                for result in results
            ],
            numeric_columns=(0, 2),
            empty_message='No results have been recorded for this round.',
        ))

    return ReportData(
        key='standings',
        title='Competition Standings',
        subtitle=(
            'Weighted overall standings and round-by-round results for the '
            'selected competition.'
        ),
        sections=sections,
        summary=[
            ('Rounds', str(len(rounds))),
            ('Participants ranked', str(len(final_rows))),
            ('Competition status', competition.get_status_display()),
        ],
        competition=competition,
        filename=f'competition-standings-{competition.id}',
    )


def report_catalog() -> list[dict]:
    """Counts and URL names for the report cards on the reports home page."""
    registrations = EventRegistration.objects.all()
    matches = Match.objects.all()
    return [
        {
            'key': 'participants',
            'title': 'Participant Register',
            'description': 'Master list of participants with category, delegation, and contact details.',
            'count': Participant.objects.count(),
            'count_label': 'participant',
            'count_label_plural': 'participants',
            'includes': ['Identity and delegation', 'Category and status', 'Registration date'],
            'csv_url': 'export_participants_csv',
            'pdf_url': 'export_participants_pdf',
            'print_url': 'print_participants',
        },
        {
            'key': 'rosters',
            'title': 'Team & Delegation Rosters',
            'description': 'Official membership, numbering, and coaching staff for every delegation.',
            'count': Team.objects.count(),
            'count_label': 'team',
            'count_label_plural': 'teams',
            'includes': ['Member numbering', 'Coaching staff', 'Approval status'],
            'csv_url': 'export_team_rosters_csv',
            'pdf_url': 'export_team_rosters_pdf',
            'print_url': 'print_team_rosters',
        },
        {
            'key': 'registrations',
            'title': 'Event Registration Register',
            'description': 'Submission and review history for online event registrations.',
            'count': registrations.count(),
            'count_label': 'registration',
            'count_label_plural': 'registrations',
            'badge': f"{registrations.filter(status=EventRegistration.Status.PENDING).count()} pending",
            'includes': ['Submission timeline', 'Review decisions', 'Target event'],
            'csv_url': 'export_registrations_csv',
            'pdf_url': 'export_registrations_pdf',
            'print_url': 'print_registrations',
        },
        {
            'key': 'schedule',
            'title': 'Official Match Schedule',
            'description': 'Complete fixture list with venues, contestants, and match status.',
            'count': matches.count(),
            'count_label': 'match',
            'count_label_plural': 'matches',
            'includes': ['Venue and timing', 'Contestants', 'Match status'],
            'csv_url': 'export_schedule_csv',
            'pdf_url': 'export_schedule_pdf',
            'print_url': 'print_schedule',
        },
        {
            'key': 'medals',
            'title': 'Medal Tally & Standings',
            'description': 'Consolidated medal count and delegation ranking across all competitions.',
            'count': Competition.objects.count(),
            'count_label': 'competition',
            'count_label_plural': 'competitions',
            'includes': ['Overall ranking', 'Per-competition breakdown', 'Medal points'],
            'csv_url': 'export_medal_tally_csv',
            'pdf_url': 'export_medal_tally_pdf',
            'print_url': 'print_medal_tally',
        },
    ]
