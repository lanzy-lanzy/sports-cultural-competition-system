import csv

from django.http import HttpResponse
from django.shortcuts import render, get_object_or_404

from accounts.access import management_required
from competitions.models import Competition
from participants.models import Participant
from registrations.models import EventRegistration
from sports.models import Match
from teams.models import Team


class UTF8Response(HttpResponse):
    """CSV response with a UTF-8 BOM so Excel opens it correctly."""

    def __init__(self, rows, filename):
        super().__init__(content_type='text/csv; charset=utf-8')
        self['Content-Disposition'] = f'attachment; filename="{filename}"'
        self.write('\ufeff'.encode('utf-8'))
        writer = csv.writer(self)
        for row in rows:
            writer.writerow([str(cell) if cell is not None else '' for cell in row])


@management_required
def reports_home(request):
    competitions = Competition.objects.all().order_by('-id')
    return render(request, 'reports/reports_home.html', {'competitions': competitions})


@management_required
def export_participants_csv(request):
    rows = [['Participant ID', 'Name', 'Email', 'Phone', 'Age', 'Category', 'Gender', 'Status', 'Team/Delegation', 'Registered']]
    for participant in Participant.objects.order_by('name'):
        rows.append([
            participant.participant_id, participant.name, participant.email, participant.phone,
            participant.age, participant.get_category_display(), participant.get_gender_display(),
            participant.status, participant.team_name, participant.registration_date,
        ])
    return UTF8Response(rows, 'participant_list.csv')


@management_required
def export_team_rosters_csv(request):
    rows = [['Team Code', 'Team Name', 'Category', 'Status', 'Member Name', 'Member #', 'Member Status', 'Coach/Manager', 'Role']]
    for team in Team.objects.select_related('created_by').order_by('name'):
        staff = list(team.staff_assignments.select_related('user'))
        memberships = list(team.memberships.select_related('participant').order_by('member_number'))
        if not memberships and not staff:
            rows.append([team.code, team.name, team.get_category_display(), team.get_status_display(), '', '', '', '', ''])
            continue
        for membership in memberships:
            staff_row = staff[0] if staff else None
            rows.append([
                team.code, team.name, team.get_category_display(), team.get_status_display(),
                membership.participant.name, membership.member_number, membership.get_status_display(),
                f"{staff_row.user.get_full_name() or staff_row.user.username}" if staff_row else '',
                staff_row.get_role_display() if staff_row else '',
            ])
    return UTF8Response(rows, 'team_rosters.csv')


@management_required
def export_registrations_csv(request):
    rows = [['Registrant', 'Contestant', 'Target', 'Type', 'Team', 'Status', 'Submitted', 'Reviewed by', 'Reviewed at']]
    for registration in EventRegistration.objects.select_related(
        'registrant', 'team', 'participant', 'competition', 'sport_event', 'reviewed_by',
    ).order_by('-created_at'):
        rows.append([
            registration.registrant.get_full_name() or registration.registrant.username,
            registration.contestant_name,
            registration.target_name,
            'Sport' if registration.sport_event_id else 'Competition',
            registration.team.name if registration.team else '',
            registration.get_status_display(),
            registration.created_at,
            registration.reviewed_by.get_full_name() if registration.reviewed_by else '',
            registration.reviewed_at,
        ])
    return UTF8Response(rows, 'event_registrations.csv')


@management_required
def export_schedule_csv(request):
    rows = [['Competition', 'Sport Event', 'Match', 'Round', 'Contestants', 'Venue', 'Start', 'End', 'Status']]
    for match in Match.objects.select_related(
        'event__competition', 'event__sport_type', 'venue',
    ).order_by('event__competition__name', 'event__name', 'scheduled_start'):
        rows.append([
            match.event.competition.name, match.event.name, match.label, match.round_number,
            match.contestants_display(),
            match.venue.name if match.venue else '',
            match.scheduled_start, match.scheduled_end, match.get_status_display(),
        ])
    return UTF8Response(rows, 'match_schedule.csv')


@management_required
def export_medal_tally_csv(request):
    from scoring.services import compute_overall_medal_tally

    rows = [['Competition', 'Rank', 'Team/Delegation', 'Gold', 'Silver', 'Bronze', 'Total Points']]

    # The overall table first, then a per-competition breakdown underneath.
    overall = compute_overall_medal_tally()
    for row in overall['rows']:
        rows.append([
            'OVERALL', row['rank'], row['name'], row['gold'], row['silver'],
            row['bronze'], row['points'],
        ])

    for entry in overall['breakdown']:
        rows.append([entry['competition'].name, '', '', '', '', '', ''])
        if not entry['rows']:
            rows.append([entry['competition'].name, '', 'No medals awarded', '', '', '', ''])
        for row in entry['rows']:
            rows.append([
                entry['competition'].name, row['rank'], row['name'], row['gold'],
                row['silver'], row['bronze'], row['points'],
            ])

    return UTF8Response(rows, 'medal_tally.csv')


@management_required
def export_judge_scores_csv(request, competition_id):
    """Per-judge, per-criterion scoring sheet for one competition."""
    from scoring.models import Score

    competition = get_object_or_404(Competition, id=competition_id)
    filename = f'judge_scores_{competition.id}.csv'

    rows = [['Round', 'Criterion', 'Max Score', 'Judge', 'Participant', 'Score', 'Remarks', 'Status', 'Scored At']]
    scores = Score.objects.filter(
        criterion__round__competition=competition,
    ).select_related(
        'criterion__round', 'judge__user', 'participant',
    ).order_by(
        'criterion__round__order', 'criterion__name', 'participant__name', 'judge_id',
    )
    for score in scores:
        judge_name = ''
        if score.judge:
            judge_name = score.judge.user.get_full_name() or score.judge.user.username
        rows.append([
            score.criterion.round.name,
            score.criterion.name,
            score.criterion.max_score,
            judge_name,
            score.participant.name,
            score.score,
            score.remarks,
            score.get_status_display(),
            score.timestamp,
        ])
    return UTF8Response(rows, filename)


@management_required
def export_standings_csv(request, competition_id):
    """Final weighted standings for one competition, plus per-round results."""
    from scoring.models import CompetitionResult
    from scoring.services import build_overall_standings

    competition = get_object_or_404(Competition, id=competition_id)
    filename = f'standings_{competition.id}.csv'

    rows = [['Competition', 'Scope', 'Rank', 'Participant', 'Score']]

    standings = build_overall_standings(competition)
    participant_lookup = {p.id: p.name for p in competition.participants.all()}
    ranked = sorted(standings.items(), key=lambda item: item[1]['rank'])
    for participant_id, data in ranked:
        rows.append([
            competition.name, 'Final (weighted)', data['rank'],
            participant_lookup.get(participant_id, f'#{participant_id}'),
            data['total'],
        ])

    for round_obj in competition.rounds.order_by('order'):
        for result in CompetitionResult.objects.filter(
            round=round_obj,
        ).select_related('participant').order_by('rank'):
            rows.append([
                competition.name, round_obj.name, result.rank,
                result.participant.name, result.total_score,
            ])

    return UTF8Response(rows, filename)