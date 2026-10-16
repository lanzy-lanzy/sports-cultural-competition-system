from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from competitions.models import Competition
from teams.models import Team, TeamMembership
from .models import Participant, ParticipantCompetition
from .forms import ParticipantForm
from . import services
from scoring.models import Score, CompetitionResult
from accounts.access import management_required, role_required
from accounts.models import UserProfile


@management_required
def participant_list(request):
    participants = Participant.objects.all().order_by('-registration_date')
    page_obj = Paginator(participants, 9).get_page(request.GET.get('page'))
    return render(request, 'participants/participant_list.html', {'page_obj': page_obj})


@management_required
def participant_detail(request, participant_id):
    participant = get_object_or_404(Participant, id=participant_id)
    participant_competitions = ParticipantCompetition.objects.filter(
        participant=participant
    ).select_related('competition').prefetch_related('competition__results').order_by('-competition__start_date')

    context = {
        'participant': participant,
        'participant_competitions': participant_competitions,
    }
    return render(request, 'participants/participant_detail.html', context)


@management_required
def create_participant(request):
    data = request.POST.copy() if request.method == 'POST' else None
    if data is not None:
        data.setdefault('category', Participant.Category.OPEN)
        data.setdefault('status', 'ACTIVE')
    form = ParticipantForm(data, request.FILES or None)
    if request.method == 'POST' and form.is_valid():
        participant = form.save()
        messages.success(request, f'Participant {participant.participant_id} was created successfully.')
        next_url = request.POST.get('next')
        if next_url and url_has_allowed_host_and_scheme(
            next_url,
            allowed_hosts={request.get_host()},
            require_https=request.is_secure(),
        ):
            return redirect(next_url)
        return redirect('participant_list')

    return render(request, 'participants/participant_management/participant_form.html', {
        'form': form,
        'form_title': 'Register participant',
        'form_description': 'Create a participant record, classification, and School ID profile.',
        'submit_label': 'Register participant',
        'next_url': request.GET.get('next', ''),
    })


@management_required
@require_POST
def delete_participant(request, participant_id):
    try:
        participant = get_object_or_404(Participant, id=participant_id)
        participant_name = participant.name

        Score.objects.filter(participant=participant).delete()
        CompetitionResult.objects.filter(participant=participant).delete()
        ParticipantCompetition.objects.filter(participant=participant).delete()

        participant.delete()

        messages.success(request, f"Successfully deleted participant: {participant_name}")
    except Exception as e:
        messages.error(request, f"Error deleting participant: {str(e)}")

    return redirect('participant_list')


@management_required
def edit_participant(request, participant_id):
    participant = get_object_or_404(Participant, id=participant_id)
    form = ParticipantForm(request.POST or None, request.FILES or None, instance=participant)
    if request.method == 'POST' and form.is_valid():
        participant = form.save(commit=False)
        if request.POST.get('remove_image') == 'true':
            participant.profile_image = None
        participant.save()
        messages.success(request, 'Participant profile updated successfully.')
        return redirect('participant_detail', participant_id=participant.id)

    return render(request, 'participants/participant_management/participant_form.html', {
        'form': form,
        'participant': participant,
        'form_title': 'Edit participant',
        'form_description': f'Update {participant.participant_id} and their participant information.',
        'submit_label': 'Save participant',
    })


def _get_or_link_participant(user):
    """Return the participant record owned by ``user``.

    A legacy participant row may pre-date account linking, so fall back to an
    unlinked row that matches the account email. The link itself is created
    when the profile form is saved.
    """
    participant = Participant.objects.filter(user=user).first()
    if participant is None and user.email:
        participant = Participant.objects.filter(
            user__isnull=True,
            email__iexact=user.email,
        ).first()
    return participant


def _joinable_teams():
    """Approved teams a participant may self-select into."""
    return Team.objects.filter(status=Team.Status.APPROVED).order_by('name')


@role_required(UserProfile.Role.PARTICIPANT)
def my_participant_profile(request):
    participant = _get_or_link_participant(request.user)

    initial = None
    if participant is None:
        middle_name = getattr(request.user.account_profile, 'middle_name', '')
        initial = {
            'first_name': request.user.first_name,
            'middle_name': middle_name,
            'last_name': request.user.last_name,
            'phone': request.user.account_profile.phone,
        }
        if not (initial['first_name'] or initial['last_name']):
            first, middle, last = ParticipantForm.split_full_name(
                request.user.get_full_name() or request.user.username
            )
            initial.update({'first_name': first, 'middle_name': middle, 'last_name': last})

    form = ParticipantForm(
        request.POST or None,
        request.FILES or None,
        instance=participant,
        initial=initial,
        self_service=True,
    )
    if request.method == 'POST' and form.is_valid():
        participant = form.save(commit=False)
        participant.user = request.user
        if not participant.email:
            # Email is captured from the authenticated account, not from the form.
            participant.email = request.user.email or f'{request.user.username}@jhcsc.edu.ph'
        participant.save()
        messages.success(request, 'Your participant profile was saved successfully.')
        return redirect('my_participant_profile')

    history = ParticipantCompetition.objects.none()
    if participant:
        history = ParticipantCompetition.objects.filter(
            participant=participant,
        ).select_related('competition').order_by('-competition__start_date')

    current_membership = None
    if participant:
        current_membership = TeamMembership.objects.filter(
            participant=participant,
        ).select_related('team').first()

    joinable_teams = [
        team for team in _joinable_teams()
        if not current_membership or team.id != current_membership.team_id
    ]

    return render(request, 'participants/my_participant_profile.html', {
        'form': form,
        'participant': participant,
        'participant_competitions': history,
        'team_membership': current_membership,
        'joinable_teams': joinable_teams,
    })


@role_required(UserProfile.Role.PARTICIPANT)
@require_POST
def select_my_team(request):
    """Let a participant self-select the team they belong to.

    Admins and team managers can still pull people onto a roster from the team
    page; this is the participant-driven counterpart and reuses the same
    TeamMembership record so both paths stay in sync.
    """
    participant = _get_or_link_participant(request.user)
    if participant is None:
        messages.error(request, 'Complete your participant profile before choosing a team.')
        return redirect('my_participant_profile')

    team_id = request.POST.get('team_id')
    team = None
    if team_id and str(team_id).isdigit():
        team = Team.objects.filter(id=team_id, status=Team.Status.APPROVED).first()
    if team is None:
        messages.error(request, 'Select a team you can join.')
        return redirect('my_participant_profile')

    with transaction.atomic():
        # A participant belongs to at most one team (OneToOne), so move the
        # membership if they already had one.
        TeamMembership.objects.filter(participant=participant).exclude(team=team).delete()
        membership, created = TeamMembership.objects.get_or_create(
            participant=participant,
            defaults={'team': team},
        )
        if not created and membership.team_id != team.id:
            membership.team = team
            membership.save(update_fields=['team'])
        participant.team_name = team.name
        participant.save(update_fields=['team_name'])

    from audit.models import record_action_from_request
    record_action_from_request(
        request,
        'TEAM_MEMBERSHIP',
        target=team,
        details=f'{participant.name} selected team "{team.name}"',
    )
    messages.success(request, f'You have joined {team.name}.')
    return redirect('my_participant_profile')


@role_required(UserProfile.Role.PARTICIPANT)
@require_POST
def leave_my_team(request):
    """Let a participant remove their own team selection."""
    participant = _get_or_link_participant(request.user)
    if participant is None:
        messages.error(request, 'No participant profile found for your account.')
        return redirect('my_participant_profile')

    membership = TeamMembership.objects.filter(participant=participant).select_related('team').first()
    if membership is None:
        messages.info(request, 'You are not currently attached to a team.')
        return redirect('my_participant_profile')

    team_name = membership.team.name
    team = membership.team
    with transaction.atomic():
        membership.delete()
        if participant.team_name == team_name:
            participant.team_name = ''
            participant.save(update_fields=['team_name'])

    from audit.models import record_action_from_request
    record_action_from_request(
        request,
        'TEAM_MEMBERSHIP',
        target=team,
        details=f'{participant.name} left team "{team_name}"',
    )
    messages.success(request, f'You have left {team_name}.')
    return redirect('my_participant_profile')


@management_required
def participant_management(request):
    competitions = Competition.objects.all().order_by('-id')
    for competition in competitions:
        competition.participant_count = competition.participants.count()

    context = {
        'competitions': competitions,
    }
    return render(request, 'participants/participant_management/participant_management.html', context)


@management_required
def manage_participants(request, competition_id):
    competition = get_object_or_404(Competition, id=competition_id)
    participants = competition.participants.all()
    available_participants = Participant.objects.exclude(competitions=competition)

    context = {
        'competition': competition,
        'participants': participants,
        'available_participants': available_participants,
    }
    return render(request, 'participants/participant_management/manage_participants.html', context)


@management_required
def assign_participants(request, competition_id):
    competition = get_object_or_404(Competition, id=competition_id)

    if request.method == 'POST':
        participant_ids = request.POST.getlist('participants')
        if not participant_ids:
            messages.error(request, 'Please select at least one participant to assign.')
            return redirect('assign_participants', competition_id=competition_id)

        assigned = services.assign_to_competition(competition, participant_ids)
        if assigned:
            messages.success(request, f'{assigned} participant(s) assigned successfully.')
        else:
            messages.warning(request, 'Selected participants are already assigned to this competition.')
        return redirect('manage_participants', competition_id=competition_id)

    available_participants = Participant.objects.exclude(competitions=competition)

    grouped_participants = {
        'male': available_participants.filter(gender='male').order_by('name'),
        'female': available_participants.filter(gender='female').order_by('name'),
        'other': available_participants.filter(gender='other').order_by('name'),
        'prefer_not_to_say': available_participants.filter(gender='prefer_not_to_say').order_by('name'),
    }

    age_ranges = []
    if available_participants.filter(age__isnull=False).exists():
        min_age = available_participants.filter(age__isnull=False).order_by('age').first().age
        max_age = available_participants.filter(age__isnull=False).order_by('-age').first().age

        current_range = min_age
        while current_range <= max_age:
            next_range = current_range + 9
            age_ranges.append({
                'start': current_range,
                'end': next_range,
                'participants': available_participants.filter(age__gte=current_range, age__lte=next_range)
            })
            current_range = next_range + 1

    context = {
        'competition': competition,
        'grouped_participants': grouped_participants,
        'age_ranges': age_ranges,
        'total_available': available_participants.count(),
    }

    return render(request, 'participants/participant_management/assign_participants.html', context)


@management_required
def remove_participant_from_competition(request, competition_id, participant_id):
    competition = get_object_or_404(Competition, id=competition_id)
    participant = get_object_or_404(Participant, id=participant_id)
    services.unassign_from_competition(competition, [participant_id])
    messages.success(request, f'Successfully removed {participant.name} from {competition.name}')
    return redirect('manage_participants', competition_id=competition_id)


# ---------------------------------------------------------------------------
# HTMX roster panel (inline assignment). Partials are returned for async
# updates so managers stay in context; the legacy full-page views above remain
# functional as a no-JS fallback.
# ---------------------------------------------------------------------------

ROSTERS_PER_PAGE = 12


def _paginate(queryset, page_param, request, per_page=ROSTERS_PER_PAGE):
    paginator = Paginator(queryset, per_page)
    return paginator.get_page(request.GET.get(page_param))


def _render_roster_panel(request, competition):
    """Render the full roster panel (both columns) for a competition."""
    assigned = services.assigned_rows(competition)
    available = services.available_participants(competition)
    return render(request, 'participants/participant_management/roster/panel.html', {
        'competition': competition,
        'assigned_page': _paginate(assigned, 'page_assigned', request),
        'available_page': _paginate(available, 'page_available', request),
        'assigned_query': request.GET.get('q_assigned', ''),
        'available_query': request.GET.get('q_available', ''),
    })


@management_required
def roster_panel(request, competition_id):
    competition = get_object_or_404(Competition, id=competition_id)
    return _render_roster_panel(request, competition)


@management_required
def roster_assigned(request, competition_id):
    competition = get_object_or_404(Competition, id=competition_id)
    query = request.GET.get('q', '')
    rows = services.assigned_rows(competition, query)
    return render(request, 'participants/participant_management/roster/assigned_list.html', {
        'competition': competition,
        'assigned_page': _paginate(rows, 'page', request),
        'assigned_query': query,
    })


@management_required
def roster_available(request, competition_id):
    competition = get_object_or_404(Competition, id=competition_id)
    query = request.GET.get('q', '')
    rows = services.available_participants(competition, query)
    return render(request, 'participants/participant_management/roster/available_list.html', {
        'competition': competition,
        'available_page': _paginate(rows, 'page', request),
        'available_query': query,
    })


@management_required
@require_POST
def roster_assign(request, competition_id):
    competition = get_object_or_404(Competition, id=competition_id)
    participant_ids = request.POST.getlist('participants')
    if not participant_ids:
        messages.warning(request, 'Select at least one participant to assign.')
    else:
        assigned = services.assign_to_competition(competition, participant_ids)
        if assigned:
            messages.success(request, f'{assigned} participant(s) assigned.')
        else:
            messages.info(request, 'Those participants are already assigned.')
    return _render_roster_panel(request, competition)


@management_required
@require_POST
def roster_unassign(request, competition_id, participant_id):
    competition = get_object_or_404(Competition, id=competition_id)
    participant = get_object_or_404(Participant, id=participant_id)
    services.unassign_from_competition(competition, [participant_id])
    messages.success(request, f'Removed {participant.name} from the roster.')
    return _render_roster_panel(request, competition)
