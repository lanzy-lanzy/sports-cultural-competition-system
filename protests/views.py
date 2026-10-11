from django.contrib.auth.models import User
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from accounts.access import management_required
from accounts.models import UserProfile
from audit.models import record_action_from_request

from .forms import ProtestForm
from .models import Protest


@login_required
def submit_protest(request):
    form = ProtestForm(request.POST or None, request.FILES or None, user=request.user)
    if request.method == 'POST' and form.is_valid():
        protest = Protest.objects.create(
            submitter=request.user,
            competition=form.cleaned_data['competition'],
            sport_event=form.cleaned_data['sport_event'],
            match=form.cleaned_data['match'],
            title=form.cleaned_data['title'],
            description=form.cleaned_data['description'],
            supporting_document=form.cleaned_data.get('supporting_document'),
        )
        messages.success(request, 'Your protest was submitted and will be reviewed by the committee.')
        return redirect('my_protests')
    return render(request, 'protests/protest_form.html', {'form': form})


@login_required
def my_protests(request):
    protests = Protest.objects.filter(submitter=request.user).select_related(
        'competition', 'sport_event', 'sport_event__sport_type', 'match', 'match__event',
    )
    return render(request, 'protests/my_protests.html', {'protests': protests})


@management_required
def protest_list(request):
    status = request.GET.get('status', '')
    protests = Protest.objects.select_related(
        'submitter', 'competition', 'sport_event', 'match', 'match__event',
    )
    if status:
        protests = protests.filter(status=status)
    status_counts = dict(protests.values_list('status').annotate(total=Count('id')))
    page_obj = Paginator(protests.order_by('-submitted_at'), 20).get_page(request.GET.get('page'))
    return render(request, 'protests/protest_list.html', {
        'page_obj': page_obj,
        'statuses': Protest.Status.choices,
        'selected_status': status,
        'status_counts': status_counts,
        'pending_count': status_counts.get(Protest.Status.SUBMITTED, 0),
    })


@management_required
def protest_detail(request, protest_id):
    protest = get_object_or_404(
        Protest.objects.select_related(
            'submitter', 'reviewed_by', 'competition', 'sport_event', 'sport_event__sport_type',
            'match', 'match__event',
        ),
        id=protest_id,
    )
    return render(request, 'protests/protest_detail.html', {
        'protest': protest,
        'statuses': Protest.Status.choices,
        'committee_members': User.objects.filter(
            account_profile__role__in=UserProfile.Role.values,
            is_active=True,
        ).order_by('username'),
    })


@management_required
def protest_review(request, protest_id):
    protest = get_object_or_404(Protest, id=protest_id)
    if request.method != 'POST':
        return redirect('protest_detail', protest_id=protest.id)

    status = request.POST.get('status')
    if status not in Protest.Status.values:
        messages.error(request, 'Invalid review status.')
        return redirect('protest_detail', protest_id=protest.id)

    protest.status = status
    protest.decision = (request.POST.get('decision') or '').strip()
    protest.reviewed_by = request.user
    protest.reviewed_at = timezone.now()
    protest.save(update_fields=['status', 'decision', 'reviewed_by', 'reviewed_at'])

    reviewer_ids = request.POST.getlist('reviewers')
    if reviewer_ids:
        protest.reviewers.set(reviewer_ids)

    record_action_from_request(
        request,
        'PROTEST_REVIEW',
        target=protest,
        details=f'{protest.title} -> {protest.get_status_display()}',
    )

    messages.success(request, f'Protest "{protest.title}" updated to {protest.get_status_display()}.')
    return redirect('protest_detail', protest_id=protest.id)