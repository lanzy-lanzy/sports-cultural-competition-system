from django.contrib import messages
from django.contrib.auth import get_user_model
from django.core.paginator import Paginator
from django.db import IntegrityError, transaction
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from accounts.access import MANAGEMENT_ROLES, get_user_role, management_required, role_required
from accounts.models import UserProfile
from announcements.services import notify_users
from competitions.models import Competition
from participants.models import Participant
from teams.models import Team, TeamMembership

from .forms import EventRegistrationForm
from .models import EventRegistration, RegistrationTemplate
from .services import (
    approve_registration,
    delete_registration,
    reject_registration,
    start_review,
    registrations_for_user,
    soft_delete_registration_template,
)


def _notify_management(title, body, link=''):
    User = get_user_model()
    admins = User.objects.filter(
        Q(is_superuser=True) | Q(account_profile__role__in=MANAGEMENT_ROLES),
        is_active=True,
    ).distinct()
    notify_users(admins, title=title, body=body, link=link)


@role_required(UserProfile.Role.PARTICIPANT, UserProfile.Role.TEAM_MANAGER)
def register_for_event(request):
    form = EventRegistrationForm(
        request.POST or None,
        user=request.user,
    )
    team_ref = request.GET.get('team', '')
    if request.method != 'POST' and (team_ref.isascii() and team_ref.isdecimal() and len(team_ref) <= 10) and 'team' in form.fields:
        if form.fields['team'].queryset.filter(pk=int(team_ref)).exists():
            form.initial['team'] = int(team_ref)

    if request.method == 'POST' and form.is_valid():
        participant = Participant.objects.filter(user=request.user).first()
        team = form.cleaned_data.get('team')

        if team is None and participant is None:
            messages.error(
                request,
                'Complete your participant profile before registering, or register your team as a team manager.',
            )
            return redirect('my_participant_profile')

        try:
            with transaction.atomic():
                registration = EventRegistration.objects.create(
                    registrant=request.user,
                    competition=form.cleaned_data['competition'],
                    sport_event=form.cleaned_data['sport_event'],
                    team=team,
                    participant=None if team else participant,
                )
        except IntegrityError:
            form.add_error(None, 'This entry has already been submitted. Check your registrations for its status.')
        else:
            _notify_management(
                title='New event registration',
                body=f'{registration.contestant_name} submitted a registration for {registration.target_name}.',
                link=reverse('registration_review_queue'),
            )
            messages.success(request, 'Your registration was submitted and is awaiting organizer approval.')
            return redirect('my_registrations')

    # A participant registers as an individual; their team affiliation already
    # comes from the "My team" selection, so surface it read-only for context.
    participant_team = None
    if get_user_role(request.user) == UserProfile.Role.PARTICIPANT:
        participant = Participant.objects.filter(user=request.user).first()
        if participant:
            membership = TeamMembership.objects.filter(
                participant=participant,
            ).select_related('team').first()
            participant_team = membership.team if membership else None

    return render(request, 'registrations/register.html', {
        'form': form,
        'participant_team': participant_team,
    })


@role_required(UserProfile.Role.PARTICIPANT, UserProfile.Role.TEAM_MANAGER)
def my_registrations(request):
    registrations = registrations_for_user(request.user).select_related(
        'competition', 'sport_event', 'sport_event__sport_type', 'team', 'participant', 'reviewed_by', 'registrant',
    )
    from teams.models import Team
    is_manager = get_user_role(request.user) == UserProfile.Role.TEAM_MANAGER
    teams = Team.objects.filter(staff_assignments__user=request.user).distinct() if is_manager else Team.objects.none()
    team_ref = request.GET.get('team', '')
    status = request.GET.get('status', '')
    if team_ref:
        registrations = registrations.filter(team_id=int(team_ref)) if (team_ref.isascii() and team_ref.isdecimal() and len(team_ref) <= 10) else registrations.none()
    if status:
        if status == 'awaiting':
            registrations = registrations.filter(status__in=['PENDING', 'UNDER_REVIEW'])
        else:
            registrations = registrations.filter(status=status) if status in EventRegistration.Status.values else registrations.none()
    page_obj = Paginator(registrations, 20).get_page(request.GET.get('page'))
    params = request.GET.copy()
    params.pop('page', None)
    return render(request, 'registrations/my_registrations.html', {
        'registrations': page_obj.object_list, 'page_obj': page_obj, 'filter_query': params.urlencode(),
        'is_team_manager': is_manager, 'managed_teams': teams,
        'selected_team': team_ref, 'selected_status': status, 'status_choices': EventRegistration.Status.choices,
    })


@management_required
def registration_review_queue(request):
    competition_id = request.GET.get('competition')
    registrations = EventRegistration.objects.select_related(
        'registrant', 'competition', 'sport_event', 'sport_event__sport_type', 'team', 'participant', 'reviewed_by',
    )
    if competition_id:
        registrations = registrations.filter(competition_id=competition_id)

    status_counts = dict(registrations.values_list('status').annotate(total=Count('id')))
    page_obj = Paginator(registrations.order_by('status', '-created_at'), 20).get_page(request.GET.get('page'))
    pending_teams = (
        Team.objects.filter(status=Team.Status.PENDING)
        .select_related('created_by')
        .prefetch_related('sports_categories')
        .order_by('-created_at')
    )
    pending_team_count = pending_teams.count()

    return render(request, 'registrations/review_queue.html', {
        'page_obj': page_obj,
        'competitions': Competition.objects.all().order_by('-id'),
        'selected_competition': int(competition_id) if competition_id else None,
        'status_counts': status_counts,
        'pending_teams': pending_teams,
        'pending_team_count': pending_team_count,
        'pending_count': status_counts.get(EventRegistration.Status.PENDING, 0) + pending_team_count,
    })


@management_required
def registration_review(request, registration_id):
    registration = get_object_or_404(
        EventRegistration.objects.select_related('registrant', 'sport_event', 'competition'),
        id=registration_id,
    )
    if request.method != 'POST':
        return redirect('registration_review_queue')

    action = request.POST.get('action')
    admin_notes = (request.POST.get('admin_notes') or '').strip()

    if action == 'delete':
        contestant_name = registration.contestant_name
        delete_registration(registration)
        from audit.models import record_action_from_request
        record_action_from_request(
            request,
            'REGISTRATION_DELETED',
            details=f'Registration deleted from review queue: {contestant_name}',
        )
        messages.success(request, f'Registration for {contestant_name} was deleted.')
        return redirect('registration_review_queue')

    if registration.status not in (
        EventRegistration.Status.PENDING,
        EventRegistration.Status.UNDER_REVIEW,
    ):
        messages.error(request, 'This registration has already been finalized.')
        return redirect('registration_review_queue')

    if action == 'review':
        if registration.status != EventRegistration.Status.PENDING:
            messages.error(request, 'Only pending registrations can be moved to review.')
        else:
            start_review(registration, request.user)
            from audit.models import record_action_from_request
            record_action_from_request(
                request,
                'REGISTRATION_REVIEW',
                target=registration,
                details=f'Review started for {registration.contestant_name}',
            )
            messages.success(request, f'Registration for {registration.contestant_name} is now under review.')
    elif action == 'approve':
        try:
            approved = approve_registration(registration, request.user, admin_notes)
        except ValueError as error:
            messages.error(request, str(error))
            return redirect('registration_review', registration_id=registration.pk)
        from audit.models import record_action_from_request
        record_action_from_request(
            request,
            'REGISTRATION_REVIEW',
            target=registration,
            details=f'Registration approved for {registration.contestant_name}',
        )
        messages.success(request, f'Registration for {registration.contestant_name} approved.')
        if approved and registration.sport_event:
            messages.success(
                request,
                f'Matches were auto-generated for {registration.sport_event.name}.',
            )
    elif action == 'reject':
        reject_registration(registration, request.user, admin_notes)
        from audit.models import record_action_from_request
        record_action_from_request(
            request,
            'REGISTRATION_REVIEW',
            target=registration,
            details=f'Registration rejected for {registration.contestant_name}',
        )
        messages.success(request, f'Registration for {registration.contestant_name} rejected.')
    else:
        messages.error(request, 'Invalid review action.')

    return redirect('registration_review_queue')


@management_required
@require_POST
def bulk_review_teams(request):
    from audit.models import record_action_from_request

    action = (request.POST.get('action') or '').strip()
    team_ids = [int(tid) for tid in request.POST.getlist('team_ids') if str(tid).isdigit()]
    if action not in ('approve', 'reject'):
        messages.error(request, 'Invalid bulk team review action.')
        return redirect('registration_review_queue')
    if not team_ids:
        messages.warning(request, 'Select at least one pending department team.')
        return redirect('registration_review_queue')

    new_status = Team.Status.APPROVED if action == 'approve' else Team.Status.REJECTED
    User = get_user_model()
    teams = list(Team.objects.filter(id__in=team_ids, status=Team.Status.PENDING))
    if not teams:
        messages.warning(request, 'No pending department teams matched your selection.')
        return redirect('registration_review_queue')

    with transaction.atomic():
        for team in teams:
            team.status = new_status
            team.save(update_fields=['status', 'updated_at'])
            record_action_from_request(
                request,
                'TEAM_STATUS',
                target=team,
                details=f'Bulk {action}: Team "{team.name}" status changed to {team.get_status_display()}',
            )
            staff_users = User.objects.filter(
                Q(id=team.created_by_id) | Q(team_staff_assignments__team=team),
                is_active=True,
            ).distinct()
            notify_users(
                staff_users,
                title=f'Team registration {team.get_status_display().lower()}',
                body=f'Your team "{team.name}" status was updated to {team.get_status_display()}.',
                link=reverse('team_detail', args=[team.id]),
            )

    verb = 'Approved' if action == 'approve' else 'Rejected'
    messages.success(request, f'{verb} {len(teams)} department team registration(s).')
    return redirect('registration_review_queue')


@management_required
@require_POST
def bulk_review_registrations(request):
    from audit.models import record_action_from_request

    action = (request.POST.get('action') or '').strip()
    reg_ids = [int(rid) for rid in request.POST.getlist('registration_ids') if str(rid).isdigit()]
    if action not in ('approve', 'reject'):
        messages.error(request, 'Invalid bulk registration action.')
        return redirect('registration_review_queue')
    if not reg_ids:
        messages.warning(request, 'Select at least one pending event registration.')
        return redirect('registration_review_queue')

    admin_notes = (request.POST.get('admin_notes') or '').strip()
    regs = list(
        EventRegistration.objects.filter(
            id__in=reg_ids,
            status__in=[EventRegistration.Status.PENDING, EventRegistration.Status.UNDER_REVIEW],
        ).select_related('registrant', 'sport_event', 'competition', 'team', 'participant')
    )
    if not regs:
        messages.warning(request, 'No pending or under-review event registrations matched your selection.')
        return redirect('registration_review_queue')

    processed = 0
    errors = []
    for reg in regs:
        try:
            if action == 'approve':
                approve_registration(reg, request.user, admin_notes)
                detail = f'Bulk approved registration for {reg.contestant_name}'
            else:
                reject_registration(reg, request.user, admin_notes)
                detail = f'Bulk rejected registration for {reg.contestant_name}'
            record_action_from_request(request, 'REGISTRATION_REVIEW', target=reg, details=detail)
            processed += 1
        except ValueError as err:
            errors.append(f'{reg.contestant_name}: {err}')

    if processed:
        verb = 'Approved' if action == 'approve' else 'Rejected'
        messages.success(request, f'{verb} {processed} event registration(s).')
    for err in errors:
        messages.error(request, err)
    return redirect('registration_review_queue')


@management_required
def registration_templates(request):
    """List and manage registration templates in the review queue view."""
    templates = RegistrationTemplate.objects.select_related(
        'competition', 'sport_event', 'participant', 'team'
    ).order_by('-created_at')

    # Handle bulk delete actions (soft or force)
    action = request.POST.get('action')
    if action == 'template_delete':
        template_id = request.POST.get('template_id')
        if template_id:
            template = get_object_or_404(RegistrationTemplate, id=template_id)
            soft_delete_registration_template(template)
            messages.success(request, f'Soft-deleted template: {template.name}')
        return redirect('registration_templates')

    if action == 'template_force_delete':
        template_id = request.POST.get('template_id')
        if template_id:
            template = get_object_or_404(RegistrationTemplate, id=template_id)
            template.delete()
            messages.success(request, f'Force-deleted template: {template.name}')
        return redirect('registration_templates')

    return render(
        request,
        'registrations/templates_admin.html',
        {
            'templates': templates,
            'status_counts': dict(templates.values_list('status').annotate(total=Count('id'))),
        },
    )


@management_required
def registration_template_action(request):
    """Handle single template delete/force-delete via POST (AJAX or form)."""
    if request.method != 'POST':
        return redirect('registration_templates')

    action = request.POST.get('action')
    template_id = request.POST.get('template_id')

    if not template_id:
        messages.error(request, 'No template selected.')
        return redirect('registration_templates')

    template = get_object_or_404(RegistrationTemplate, id=template_id)

    if action == 'template_delete':
        soft_delete_registration_template(template)
        messages.success(request, f'Soft-deleted template: {template.name}')
    elif action == 'template_force_delete':
        template.delete()
        messages.success(request, f'Force-deleted template: {template.name}')
    else:
        messages.error(request, 'Invalid action.')

    return redirect('registration_templates')
