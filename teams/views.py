from django.contrib import messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.db.models.deletion import ProtectedError
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods, require_POST

from accounts.access import MANAGEMENT_ROLES, get_user_role, role_required
from accounts.models import UserProfile
from .forms import (
    TeamEventRosterForm, TeamForm, TeamMembershipForm, TeamMemberEventsForm,
    TeamRosterFilterForm, TeamStaffForm,
)
from .models import Team, TeamMembership, TeamStaff
from .services import save_team_event_roster


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
    return render(request, 'teams/team_list.html', {'teams': teams, 'can_delete_teams': get_user_role(request.user) in MANAGEMENT_ROLES})


@team_editor_required
def create_team(request):
    can_approve = get_user_role(request.user) in MANAGEMENT_ROLES
    form = TeamForm(
        request.POST or None,
        request.FILES or None,
        allow_status=can_approve,
        force_approved=can_approve,
    )
    roster_form = _event_roster_form(request, form.instance) if can_approve else None
    team = _save_team_form(request, form, roster_form)
    if team is not None:
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
        'roster_form': roster_form,
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
    roster_form = _event_roster_form(request, team) if can_approve else None
    if _save_team_form(request, form, roster_form) is not None:
        messages.success(request, 'Team details updated successfully.')
        return redirect('team_detail', team_id=team.id)
    return render(request, 'teams/team_form.html', {'form': form, 'team': team, 'roster_form': roster_form})


def _event_roster_form(request, team):
    return TeamEventRosterForm(
        request.POST if request.method == 'POST' else None,
        team=team,
        prefix='event-players',
    )


def _save_team_form(request, form, roster_form):
    if request.method != 'POST':
        return None
    valid = form.is_valid()
    roster_valid = roster_form is None or roster_form.is_valid()
    if not (valid and roster_valid):
        return None

    team = form.save(commit=False)
    creating = team.pk is None
    if creating:
        team.created_by = request.user
    selections = roster_form.selections() if roster_form is not None else {}
    try:
        with transaction.atomic():
            team.save()
            form.save_m2m()
            if creating and get_user_role(request.user) == UserProfile.Role.TEAM_MANAGER:
                TeamStaff.objects.create(team=team, user=request.user, role=TeamStaff.Role.MANAGER)
            if selections:
                save_team_event_roster(team, selections, request.user)
    except ValidationError as error:
        roster_form.add_error(None, error)
    except IntegrityError:
        form.add_error(None, 'The team or roster changed while you were editing. Reload and try again.')
    else:
        return team
    return None


@team_editor_required
@require_http_methods(['GET', 'HEAD', 'POST'])
def team_detail(request, team_id):
    team = _get_accessible_team(request.user, team_id)
    can_approve = get_user_role(request.user) in MANAGEMENT_ROLES
    can_assign = can_approve and team.category != Team.Category.CULTURAL
    if request.method == 'POST' and not can_assign:
        raise PermissionDenied
    roster_form = None
    if can_assign:
        roster_form = TeamEventRosterForm(
            request.POST if request.method == 'POST' else None,
            team=team, prefix='event-players', selected_sports_only=True,
        )
        if request.method == 'POST' and roster_form.is_valid():
            try:
                with transaction.atomic():
                    locked_team = Team.objects.select_for_update().get(pk=team.pk)
                    save_team_event_roster(locked_team, roster_form.selections(), request.user)
            except ValidationError as error:
                roster_form.add_error(None, error)
            except IntegrityError:
                roster_form.add_error(None, 'The roster changed while you were editing. Reload and try again.')
            else:
                messages.success(request, 'Event assignments saved.')
                return redirect('team_detail', team_id=team.pk)
    from sports.services import compute_team_standings
    memberships = team.memberships.select_related('participant').prefetch_related('events__competition').order_by(
        'participant__name', 'pk',
    )
    total_members = memberships.count()
    filter_form = TeamRosterFilterForm(request.GET)
    if filter_form.is_valid():
        filters = filter_form.cleaned_data
        query = filters['q']
        if query:
            search = Q(participant__name__icontains=query) | Q(
                participant__participant_id__icontains=query,
            )
            if query.isascii() and query.isdecimal() and len(query) <= 10:
                search |= Q(member_number=int(query))
            memberships = memberships.filter(search)
        if filters['status']:
            memberships = memberships.filter(status=filters['status'])
        if filters['category']:
            memberships = memberships.filter(participant__category=filters['category'])
        if filters['gender']:
            memberships = memberships.filter(participant__gender=filters['gender'])
    else:
        memberships = memberships.none()
    page_obj = Paginator(memberships, 25).get_page(request.GET.get('page'))
    for membership in page_obj.object_list:
        membership.events_form = TeamMemberEventsForm(membership=membership, prefix=f'member-{membership.pk}')
    query_params = request.GET.copy()
    query_params.pop('page', None)
    return render(request, 'teams/team_detail.html', {
        'team': team,
        'roster_form': roster_form,
        'sports_standings': compute_team_standings(team),
        'memberships': page_obj.object_list,
        'page_obj': page_obj,
        'total_members': total_members,
        'filter_form': filter_form,
        'filter_query': query_params.urlencode(),
        'staff_assignments': team.staff_assignments.select_related('user'),
        'membership_form': TeamMembershipForm(team=team),
        'staff_form': TeamStaffForm(),
        'can_approve_teams': can_approve,
    }, status=400 if request.method == 'POST' else 200)


@team_editor_required
@require_POST
@transaction.atomic
def add_team_member(request, team_id):
    team = _get_accessible_team(request.user, team_id)
    form = TeamMembershipForm(request.POST, team=team)
    if form.is_valid():
        try:
            with transaction.atomic():
                Team.objects.select_for_update().get(pk=team.pk)
                membership = form.save(commit=False)
                membership.team = team
                membership.save()
                membership.participant.team_name = team.name
                membership.participant.save(update_fields=['team_name'])
                from .services import set_member_events
                set_member_events(membership, form.cleaned_data['events'], request.user)
        except ValidationError as error:
            messages.error(request, ' '.join(error.messages))
        except IntegrityError:
            messages.error(request, 'That player or jersey number is already assigned. Refresh the roster and try again.')
        else:
            messages.success(request, f'{membership.participant.name} was added to the roster.')
    else:
        messages.error(request, ' '.join(str(error) for errors in form.errors.values() for error in errors))
    return redirect('team_detail', team_id=team.id)


@team_editor_required
@require_POST
def update_member_events(request, team_id, membership_id):
    team = _get_accessible_team(request.user, team_id)
    membership = get_object_or_404(TeamMembership.objects.select_related('team', 'participant'), pk=membership_id, team=team)
    form = TeamMemberEventsForm(request.POST, membership=membership, prefix=f'member-{membership.pk}')
    if form.is_valid():
        from .services import set_member_events
        try:
            set_member_events(membership, form.cleaned_data['events'], request.user)
        except ValidationError as error:
            form.add_error('events', error)
        else:
            messages.success(request, f'Event assignments updated for {membership.participant.name}.')
            return redirect('team_detail', team_id=team.pk)
    return render(request, 'teams/member_events.html', {'team': team, 'membership': membership, 'form': form}, status=400)


def _selected_ids(request):
    values = request.POST.getlist('selected')
    if not values or len(values) > 500:
        raise ValidationError('Select between 1 and 500 items.')
    try:
        ids = {int(value) for value in values}
    except (ValueError, TypeError):
        raise ValidationError('Invalid selection.')
    if any(pk < 1 for pk in ids):
        raise ValidationError('Invalid selection.')
    return ids


@team_editor_required
@require_POST
def bulk_delete_teams(request):
    _require_management(request.user)
    from .services import force_delete_teams
    try:
        ids = _selected_ids(request)
        items = list(_accessible_teams(request.user).filter(pk__in=ids))
        if len(items) != len(ids):
            raise ValidationError('Select valid teams.')
        if request.POST.get('confirm') != 'yes':
            return render(request, 'teams/bulk_delete_confirm.html', {'items': items, 'kind': 'teams', 'cancel_url': 'team_list'})
        count = force_delete_teams(ids, request.user)
        messages.success(request, f'{count} team(s) permanently deleted.')
    except ValidationError as error:
        messages.error(request, ' '.join(error.messages))
    except ProtectedError:
        messages.error(request, 'These teams have protected award records. Reopen the affected events and withdraw medals before deleting teams. Nothing was deleted.')
    return redirect('team_list')


@team_editor_required
@require_POST
def bulk_delete_members(request, team_id):
    team = _get_accessible_team(request.user, team_id)
    from .services import force_delete_memberships
    try:
        ids = _selected_ids(request)
        items = list(team.memberships.filter(pk__in=ids).select_related('participant'))
        if len(items) != len(ids):
            raise ValidationError('Select members belonging to this team.')
        if request.POST.get('confirm') != 'yes':
            return render(request, 'teams/bulk_delete_confirm.html', {'items': items, 'kind': 'members', 'team': team})
        count = force_delete_memberships(team, ids, request.user)
        messages.success(request, f'{count} roster membership(s) permanently removed. Player profiles were retained.')
    except ValidationError as error:
        messages.error(request, ' '.join(error.messages))
    return redirect('team_detail', team_id=team.pk)


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
