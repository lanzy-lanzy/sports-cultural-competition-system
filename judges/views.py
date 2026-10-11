from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator

from competitions.models import Competition, Round
from participants.models import Participant
from scoring.models import Score
from .models import Judge, JudgeAssignment
from accounts.access import judge_required, management_required


@judge_required
def judge_profile(request):
    judge = get_object_or_404(Judge, user=request.user)

    if request.method == 'POST':
        judge.phone = request.POST.get('phone', judge.phone)
        judge.expertise = request.POST.get('expertise', judge.expertise)
        judge.bio = request.POST.get('bio', judge.bio)

        if 'profile_image' in request.FILES:
            judge.profile_image = request.FILES['profile_image']
        elif request.POST.get('remove_image') == 'true':
            judge.profile_image = None

        judge.save()
        messages.success(request, 'Profile updated successfully!')
        return redirect('judge_profile')

    assignments = JudgeAssignment.objects.filter(judge=judge).select_related('competition').order_by('-assigned_at')
    for assignment in assignments:
        assignment.rounds_list = assignment.rounds.all().order_by('order')

    context = {
        'judge': judge,
        'assignments': assignments,
    }
    return render(request, 'judges/judge/profile.html', context)


@management_required
def judge_management(request):
    competitions = Competition.objects.all().order_by('-id')
    for competition in competitions:
        competition.judge_count = JudgeAssignment.objects.filter(competition=competition).count()

    page_obj = Paginator(competitions, 9).get_page(request.GET.get('page'))

    context = {
        'competitions': page_obj,
        'page_obj': page_obj,
    }
    return render(request, 'judges/judge_management/judge_management.html', context)


@management_required
def manage_judges(request, competition_id):
    competition = get_object_or_404(Competition, id=competition_id)
    assignments = JudgeAssignment.objects.filter(competition=competition).order_by('id')
    page_obj = Paginator(assignments, 10).get_page(request.GET.get('page'))
    available_judges = Judge.objects.filter(status='ACTIVE')
    competition_rounds = Round.objects.filter(competition=competition)

    context = {
        'competition': competition,
        'assignments': page_obj,
        'page_obj': page_obj,
        'available_judges': available_judges,
        'competition_rounds': competition_rounds,
    }
    return render(request, 'judges/judge_management/manage_judges.html', context)


@management_required
def assign_judges(request, competition_id):
    competition = get_object_or_404(Competition, id=competition_id)

    if request.method == 'POST':
        judge_ids = request.POST.getlist('judges')
        round_ids = request.POST.getlist('rounds')

        if not judge_ids:
            messages.error(request, 'Please select at least one judge.')
            return redirect('manage_judges', competition_id=competition_id)

        if not round_ids:
            messages.error(request, 'Please select at least one round.')
            return redirect('manage_judges', competition_id=competition_id)

        judges = Judge.objects.filter(id__in=judge_ids)
        rounds = Round.objects.filter(id__in=round_ids)

        for judge in judges:
            assignment, created = JudgeAssignment.objects.get_or_create(
                judge=judge,
                competition=competition,
                defaults={'status': 'ACTIVE'}
            )
            assignment.rounds.set(rounds)

        messages.success(request, 'Judges assigned successfully!')
        return redirect('manage_judges', competition_id=competition_id)

    available_judges = Judge.objects.filter(status='ACTIVE')
    competition_rounds = Round.objects.filter(competition=competition)

    context = {
        'competition': competition,
        'available_judges': available_judges,
        'competition_rounds': competition_rounds,
    }
    return render(request, 'judges/judge_management/assign_judges.html', context)


@management_required
def edit_judge_assignment(request, competition_id, assignment_id):
    competition = get_object_or_404(Competition, id=competition_id)
    assignment = get_object_or_404(JudgeAssignment, id=assignment_id, competition=competition)

    if request.method == 'POST':
        round_ids = request.POST.getlist('rounds')
        status = request.POST.get('status')

        if not round_ids:
            messages.error(request, 'Please select at least one round.')
            return redirect('edit_judge_assignment', competition_id=competition_id, assignment_id=assignment_id)

        rounds = Round.objects.filter(id__in=round_ids)
        assignment.rounds.set(rounds)
        assignment.status = status
        assignment.save()

        messages.success(request, 'Judge assignment updated successfully!')
        return redirect('manage_judges', competition_id=competition_id)

    competition_rounds = Round.objects.filter(competition=competition)
    context = {
        'competition': competition,
        'assignment': assignment,
        'competition_rounds': competition_rounds,
    }
    return render(request, 'judges/judge_management/edit_assignment.html', context)


@management_required
def delete_judge_assignment(request, competition_id, assignment_id):
    assignment = get_object_or_404(JudgeAssignment, id=assignment_id, competition_id=competition_id)
    assignment.delete()
    messages.success(request, 'Judge assignment deleted successfully.')
    return redirect('manage_judges', competition_id=competition_id)


@judge_required
def judge_history(request):
    judge = get_object_or_404(Judge, user=request.user)

    assigned_round_ids = JudgeAssignment.objects.filter(
        judge=judge
    ).values_list('rounds__id', flat=True)

    rounds = Round.objects.filter(
        id__in=assigned_round_ids
    ).select_related('competition').prefetch_related('criteria').order_by('-competition__start_date', 'order')

    history_data = []
    for round_obj in rounds:
        criteria = round_obj.criteria.all()

        participant_ids = Score.objects.filter(
            judge=judge,
            criterion__round=round_obj,
            status='SUBMITTED'
        ).values_list('participant_id', flat=True).distinct()

        participants = Participant.objects.filter(id__in=participant_ids).order_by('name')

        participants_data = []
        for participant in participants:
            scores = Score.objects.filter(
                judge=judge,
                participant=participant,
                criterion__round=round_obj,
                status='SUBMITTED'
            )
            criteria_scores = {score.criterion_id: score.score for score in scores}
            total = sum(criteria_scores.values())
            submitted_count = scores.count()

            participants_data.append({
                'participant': participant,
                'criteria_scores': criteria_scores,
                'total': total,
                'submitted': submitted_count == criteria.count() if criteria.count() else False,
            })

        if participants_data:
            history_data.append({
                'competition': round_obj.competition,
                'round': round_obj,
                'criteria': criteria,
                'participants': participants_data,
            })

    page_obj = Paginator(history_data, 6).get_page(request.GET.get('page'))

    context = {
        'judge': judge,
        'history_data': page_obj,
        'page_obj': page_obj,
    }
    return render(request, 'judges/judge/history.html', context)


@judge_required
def judge_dashboard(request):
    judge = get_object_or_404(Judge, user=request.user)

    assigned_competitions = Competition.objects.filter(
        status='ACTIVE',
        judge_assignments__judge=judge,
        judge_assignments__status='ACTIVE'
    ).prefetch_related('rounds')

    competition_data = []
    for competition in assigned_competitions:
        assigned_rounds = competition.rounds.filter(
            judge_assignments__judge=judge
        ).order_by('order')

        competition_data.append({
            'competition': competition,
            'rounds': assigned_rounds,
            'participant_count': competition.participants.count(),
        })

    context = {
        'judge': judge,
        'competition_data': competition_data,
        'pending_scores': Score.objects.filter(judge=judge, status='DRAFT').count(),
        'submitted_scores': Score.objects.filter(judge=judge, status='SUBMITTED').count(),
    }
    return render(request, 'judges/judge/dashboard.html', context)
