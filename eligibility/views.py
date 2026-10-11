from django.contrib import messages
from django.core.paginator import Paginator
from django.db import models
from django.db.models import Count
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from accounts.access import management_required, role_required
from accounts.models import UserProfile
from competitions.models import Competition
from participants.models import Participant, ParticipantCompetition

from .forms import EligibilitySubmissionForm
from .models import EligibilityRecord


@role_required(UserProfile.Role.PARTICIPANT)
def my_eligibility(request):
    participant = Participant.objects.filter(user=request.user).first()
    if participant is None:
        messages.error(request, 'Complete your athlete profile before submitting eligibility records.')
        return redirect('my_participant_profile')

    form = EligibilitySubmissionForm(
        request.POST or None,
        request.FILES or None,
        participant=participant,
    )
    if request.method == 'POST' and form.is_valid():
        record = form.save(commit=False)
        record.participant = participant
        record.status = EligibilityRecord.Status.PENDING
        record.save()
        messages.success(
            request,
            f'Eligibility record submitted for {record.competition.name}. An organizer will review it.',
        )
        return redirect('my_eligibility')

    records = participant.eligibility_records.select_related('competition', 'reviewed_by')
    return render(request, 'eligibility/my_eligibility.html', {
        'participant': participant,
        'records': records,
        'form': form,
    })


@management_required
def eligibility_list(request):
    competition_id = request.GET.get('competition')
    records = EligibilityRecord.objects.select_related('participant', 'competition', 'reviewed_by')
    if competition_id:
        records = records.filter(competition_id=competition_id)

    status_counts = dict(records.values_list('status').annotate(total=Count('id')))
    page_obj = Paginator(records.order_by('status', '-submitted_at'), 20).get_page(request.GET.get('page'))

    return render(request, 'eligibility/eligibility_list.html', {
        'page_obj': page_obj,
        'competitions': Competition.objects.all().order_by('-id'),
        'selected_competition': int(competition_id) if competition_id else None,
        'status_counts': status_counts,
        'pending_count': status_counts.get(EligibilityRecord.Status.PENDING, 0),
    })


@management_required
@require_POST
def eligibility_review(request, record_id):
    record = get_object_or_404(
        EligibilityRecord.objects.select_related('participant', 'competition'),
        id=record_id,
    )
    action = request.POST.get('action')

    if action == 'approve':
        record.status = EligibilityRecord.Status.APPROVED
    elif action == 'reject':
        record.status = EligibilityRecord.Status.REJECTED
    else:
        messages.error(request, 'Invalid review action.')
        return redirect('eligibility_list')

    record.reviewed_by = request.user
    record.reviewed_at = timezone.now()
    record.notes = (request.POST.get('notes') or '').strip()
    record.save(update_fields=['status', 'reviewed_by', 'reviewed_at', 'notes'])

    from audit.models import record_action_from_request
    record_action_from_request(
        request,
        'ELIGIBILITY_REVIEW',
        target=record,
        details=f'Eligibility {record.get_status_display().lower()} for {record.participant.name} in {record.competition.name}',
    )

    if action == 'approve' and not ParticipantCompetition.objects.filter(
        participant=record.participant,
        competition=record.competition,
    ).exists():
        next_number = (
            ParticipantCompetition.objects.filter(competition=record.competition)
            .aggregate(highest=models.Max('number'))['highest']
            or 0
        ) + 1
        ParticipantCompetition.objects.create(
            participant=record.participant,
            competition=record.competition,
            number=next_number,
        )
    messages.success(
        request,
        f'Eligibility for {record.participant.name} in {record.competition.name} '
        f'was {record.get_status_display().lower()}.',
    )
    return redirect(f'{reverse("eligibility_list")}?competition={record.competition_id}')
