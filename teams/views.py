from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from accounts.access import MANAGEMENT_ROLES, get_user_role, role_required
from accounts.models import UserProfile
from .forms import TeamForm, TeamMembershipForm, TeamStaffForm
from .models import Team, TeamMembership, TeamStaff


TEAM_EDITOR_ROLES = MANAGEMENT_ROLES | {UserProfile.Role.TEAM_MANAGER}
team_editor_required = role_required(*TEAM_EDITOR_ROLES)


def _accessible_teams(user):
    teams = Team.objects.prefetch_related('memberships__participant', 'staff_assignments__user')
    if get_user_role(user) in MANAGEMENT_ROLES:
        return teams
    return teams.filter(staff_assignments__user=user).distinct()


def _get_accessible_team(user, team_id):
    return get_object_or_404(_accessible_teams(user), id=team_id)


def _require_management(user):
    if get_user_role(user) not in MANAGEMENT_ROLES:
        raise PermissionDenied('Only competition management can change team staff or approval status.')


@team_editor_required
def team_list(request):
    teams = _accessible_teams(request.user).order_by('name')
    return render(request, 'teams/team_list.html', {'teams': teams})


@team_editor_required
def create_team(request):
    can_approve = get_user_role(request.user) in MANAGEMENT_ROLES
    form = TeamForm(
        request.POST or None,
        request.FILES or None,
        allow_status=can_approve,
        force_approved=can_approve,
    )
    if request.method == 'POST' and form.is_valid():
        with transaction.atomic():
            team = form.save(commit=False)
            team.created_by = request.user
            if not can_approve:
                team.status = Team.Status.PENDING
            team.save()
            if get_user_role(request.user) == UserProfile.Role.TEAM_MANAGER:
                TeamStaff.objects.create(team=team, user=request.user, role=TeamStaff.Role.MANAGER)
        if can_approve:
            messages.success(
                request,
                f'{team.name} was created with code {team.code} and is approved.',
            )
        else:
            messages.success(
                request,
                f'{team.name} was created with code {team.code}. '
                'It is awaiting approval from competition management.',
            )
        return redirect('team_detail', team_id=team.id)
    return render(request, 'teams/team_form.html', {
        'form': form,
        'team': None,
        'auto_approved': can_approve,
    })


@team_editor_required
def edit_team(request, team_id):
    team = _get_accessible_team(request.user, team_id)
    can_approve = get_user_role(request.user) in MANAGEMENT_ROLES
    form = TeamForm(
        request.POST or None,
        request.FILES or None,
        instance=team,
        allow_status=can_approve,
    )
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Team details updated successfully.')
        return redirect('team_detail', team_id=team.id)
    return render(request, 'teams/team_form.html', {'form': form, 'team': team})


@team_editor_required
def team_detail(request, team_id):
    team = _get_accessible_team(request.user, team_id)
    return render(request, 'teams/team_detail.html', {
        'team': team,
        'memberships': team.memberships.select_related('participant'),
        'staff_assignments': team.staff_assignments.select_related('user'),
        'membership_form': TeamMembershipForm(team=team),
        'staff_form': TeamStaffForm(),
        'can_approve_teams': get_user_role(request.user) in MANAGEMENT_ROLES,
    })


@team_editor_required
@require_POST
def add_team_member(request, team_id):
    team = _get_accessible_team(request.user, team_id)
    form = TeamMembershipForm(request.POST, team=team)
    if form.is_valid():
        membership = form.save(commit=False)
        membership.team = team
        membership.save()
        membership.participant.team_name = team.name
        membership.participant.save(update_fields=['team_name'])
        messages.success(request, f'{membership.participant.name} was added to the roster.')
    else:
        messages.error(request, 'The participant could not be added. Check the roster details.')
    return redirect('team_detail', team_id=team.id)


@team_editor_required
@require_POST
def remove_team_member(request, team_id, membership_id):
    team = _get_accessible_team(request.user, team_id)
    membership = get_object_or_404(TeamMembership, id=membership_id, team=team)
    participant = membership.participant
    membership.delete()
    if participant.team_name == team.name:
        participant.team_name = ''
        participant.save(update_fields=['team_name'])
    messages.success(request, f'{participant.name} was removed from the roster.')
    return redirect('team_detail', team_id=team.id)


@team_editor_required
@require_POST
def add_team_staff(request, team_id):
    _require_management(request.user)
    team = _get_accessible_team(request.user, team_id)
    form = TeamStaffForm(request.POST)
    if form.is_valid():
        assignment, created = TeamStaff.objects.get_or_create(
            team=team,
            user=form.cleaned_data['user'],
            role=form.cleaned_data['role'],
        )
        if created:
            messages.success(request, 'Coach or team manager assigned successfully.')
        else:
            messages.info(request, 'That staff assignment already exists.')
    else:
        messages.error(request, 'Select a valid coach or team manager.')
    return redirect('team_detail', team_id=team.id)


@team_editor_required
@require_POST
def remove_team_staff(request, team_id, assignment_id):
    _require_management(request.user)
    team = _get_accessible_team(request.user, team_id)
    assignment = get_object_or_404(TeamStaff, id=assignment_id, team=team)
    assignment.delete()
    messages.success(request, 'Team staff assignment removed.')
    return redirect('team_detail', team_id=team.id)


@team_editor_required
@require_POST
def update_team_status(request, team_id):
    _require_management(request.user)
    team = _get_accessible_team(request.user, team_id)
    status = request.POST.get('status')
    if status not in Team.Status.values:
        messages.error(request, 'Invalid team status.')
    else:
        team.status = status
        team.save(update_fields=['status', 'updated_at'])
        from audit.models import record_action_from_request
        record_action_from_request(
            request,
            'TEAM_STATUS',
            target=team,
            details=f'Team "{team.name}" status changed to {team.get_status_display()}',
        )
        messages.success(request, f'Team status changed to {team.get_status_display()}.')
    return redirect('team_detail', team_id=team.id)
