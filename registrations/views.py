from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Count
from django.shortcuts import get_object_or_404, redirect, render

from accounts.access import management_required, role_required
from accounts.models import UserProfile
from competitions.models import Competition
from participants.models import Participant

from .forms import EventRegistrationForm
from .models import EventRegistration
from .services import approve_registration, reject_registration, start_review


@role_required(UserProfile.Role.PARTICIPANT, UserProfile.Role.TEAM_MANAGER)
def register_for_event(request):
    form = EventRegistrationForm(
        request.POST or None,
        request.FILES or None,
        user=request.user,
    )

    if request.method == 'POST' and form.is_valid():
        participant = Participant.objects.filter(user=request.user).first()
        team = form.cleaned_data['team']

        if team is None and participant is None:
            messages.error(
                request,
                'Complete your participant profile before registering, or register your team as a team manager.',
            )
            return redirect('my_participant_profile')

        EventRegistration.objects.create(
            registrant=request.user,
            competition=form.cleaned_data['competition'],
            sport_event=form.cleaned_data['sport_event'],
            team=team,
            participant=participant,
            requirements_document=form.cleaned_data.get('requirements_document'),
            notes=form.cleaned_data['notes'],
        )
        messages.success(request, 'Your registration was submitted and is awaiting organizer approval.')
        return redirect('my_registrations')

    return render(request, 'registrations/register.html', {'form': form})


@role_required(UserProfile.Role.PARTICIPANT, UserProfile.Role.TEAM_MANAGER)
def my_registrations(request):
    registrations = EventRegistration.objects.filter(registrant=request.user).select_related(
        'competition', 'sport_event', 'sport_event__sport_type', 'team', 'participant', 'reviewed_by',
    )
    return render(request, 'registrations/my_registrations.html', {'registrations': registrations})


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

    return render(request, 'registrations/review_queue.html', {
        'page_obj': page_obj,
        'competitions': Competition.objects.all().order_by('-id'),
        'selected_competition': int(competition_id) if competition_id else None,
        'status_counts': status_counts,
        'pending_count': status_counts.get(EventRegistration.Status.PENDING, 0),
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
        approve_registration(registration, request.user, admin_notes)
        from audit.models import record_action_from_request
        record_action_from_request(
            request,
            'REGISTRATION_REVIEW',
            target=registration,
            details=f'Registration approved for {registration.contestant_name}',
        )
        messages.success(request, f'Registration for {registration.contestant_name} approved.')
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
