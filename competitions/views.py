from decimal import Decimal, InvalidOperation
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction, models
from django.core.paginator import Paginator
from django.views.decorators.http import require_POST

from .models import Competition, Round, Criterion
from scoring.services import calculate_rankings
from django.db.models import Count
from accounts.access import MANAGEMENT_ROLES, get_user_role, management_required


def _parse_decimal(raw, default=None):
    if raw in (None, ''):
        return default
    try:
        value = Decimal(raw)
    except (InvalidOperation, TypeError):
        return default
    if not value.is_finite():
        return default
    return value


def _competition_extras(post):
    """Fields shared by create/edit competition forms for kinds and medals."""
    kind = post.get('kind')
    if kind not in Competition.Kind.values:
        kind = Competition.Kind.MIXED
    event_type = post.get('cultural_event_type')
    if event_type not in Competition.CulturalEventType.values:
        event_type = ''
    return {
        'kind': kind,
        'cultural_event_type': event_type,
        'gold_points': _parse_decimal(post.get('gold_points'), Decimal('10')),
        'silver_points': _parse_decimal(post.get('silver_points'), Decimal('5')),
        'bronze_points': _parse_decimal(post.get('bronze_points'), Decimal('3')),
    }


@login_required
def competition_list(request):
    competitions = Competition.objects.all().order_by('-id').annotate(
        rounds_count=Count('rounds', distinct=True),
        criteria_count=Count('rounds__criteria', distinct=True),
    )
    if get_user_role(request.user) not in MANAGEMENT_ROLES:
        competitions = competitions.filter(status__in=['ACTIVE', 'COMPLETED'])
    page_obj = Paginator(competitions, 9).get_page(request.GET.get('page'))
    return render(request, 'competitions/competition_list.html', {'page_obj': page_obj})


@login_required
def competition_detail(request, competition_id):
    competitions = Competition.objects.all()
    if get_user_role(request.user) not in MANAGEMENT_ROLES:
        competitions = competitions.filter(status__in=['ACTIVE', 'COMPLETED'])
    competition = get_object_or_404(competitions, id=competition_id)
    rounds = competition.rounds.all().prefetch_related('criteria').order_by('order')

    context = {
        'competition': competition,
        'rounds': rounds,
        'total_criteria': sum(round.criteria.count() for round in rounds),
        'total_max_score': sum(
            criterion.max_score
            for round in rounds
            for criterion in round.criteria.all()
        )
    }
    return render(request, 'competitions/competition_detail.html', context)


@management_required
def create_competition(request):
    if request.method == 'POST':
        try:
            with transaction.atomic():
                competition = Competition.objects.create(
                    name=request.POST.get('name').upper(),
                    description=request.POST.get('description').upper(),
                    start_date=request.POST.get('start_date'),
                    end_date=request.POST.get('end_date'),
                    status=request.POST.get('status'),
                    created_by=request.user,
                    **_competition_extras(request.POST)
                )

                round_names = request.POST.getlist('round_names[]')
                round_orders = request.POST.getlist('round_orders[]')
                round_weights = request.POST.getlist('round_weights[]')
                round_statuses = request.POST.getlist('round_statuses[]')

                for i in range(len(round_names)):
                    if round_names[i].strip():
                        round_obj = Round.objects.create(
                            competition=competition,
                            name=round_names[i].upper(),
                            order=int(round_orders[i]) if round_orders[i] else i + 1,
                            weight_percentage=float(round_weights[i]) if round_weights[i] else 100,
                            status=round_statuses[i] if round_statuses[i] else 'PENDING'
                        )

                        prefix = f'criterion_names_{i+1}[]'
                        criterion_names = request.POST.getlist(prefix)
                        desc_prefix = f'criterion_descriptions_{i+1}[]'
                        criterion_descriptions = request.POST.getlist(desc_prefix)
                        score_prefix = f'criterion_max_scores_{i+1}[]'
                        criterion_max_scores = request.POST.getlist(score_prefix)
                        weight_prefix = f'criterion_weights_{i+1}[]'
                        criterion_weights = request.POST.getlist(weight_prefix)

                        for j in range(len(criterion_names)):
                            if criterion_names[j].strip():
                                Criterion.objects.create(
                                    round=round_obj,
                                    name=criterion_names[j].upper(),
                                    description=criterion_descriptions[j].upper() if j < len(criterion_descriptions) and criterion_descriptions[j] else '',
                                    max_score=float(criterion_max_scores[j]) if j < len(criterion_max_scores) and criterion_max_scores[j] else 100,
                                    weight_percentage=_parse_decimal(
                                        criterion_weights[j] if j < len(criterion_weights) else '',
                                        Decimal('0'),
                                    )
                                )

            messages.success(request, 'Competition created successfully!')
            return redirect('competition_list')
        except Exception as e:
            messages.error(request, f'Error creating competition: {str(e)}')
            return render(request, 'competitions/create_competition.html')

    return render(request, 'competitions/create_competition.html')


@management_required
def edit_competition(request, competition_id):
    competition = get_object_or_404(Competition, id=competition_id)

    if request.method == 'POST':
        title = request.POST.get('title')
        description = request.POST.get('description')
        start_date = request.POST.get('start_date')
        end_date = request.POST.get('end_date')
        status = request.POST.get('status')

        competition.name = title.upper()
        competition.description = description.upper()
        competition.start_date = start_date
        competition.end_date = end_date
        competition.status = status
        for key, value in _competition_extras(request.POST).items():
            setattr(competition, key, value)
        competition.save()

        messages.success(request, 'Competition updated successfully!')
        return redirect('competition_detail', competition_id=competition.id)

    return render(request, 'competitions/edit_competition.html', {'competition': competition})


@management_required
def delete_competition(request, competition_id):
    if request.method == 'POST':
        competition = get_object_or_404(Competition, id=competition_id)
        competition.delete()
        messages.success(request, 'Competition deleted successfully.')
        return redirect('competition_list')
    return redirect('competition_list')


@management_required
def toggle_competition_status(request, competition_id):
    if request.method == 'POST':
        competition = get_object_or_404(Competition, id=competition_id)

        status_flow = {
            'PENDING': 'DRAFT',
            'DRAFT': 'ACTIVE',
            'ACTIVE': 'COMPLETED',
            'COMPLETED': 'DRAFT'
        }

        competition.status = status_flow.get(competition.status, 'DRAFT')
        competition.save()

        messages.success(request, f'Competition status updated to {competition.status}')
        return redirect('competition_list')


@management_required
def manage_rounds(request, competition_id):
    competition = get_object_or_404(Competition, id=competition_id)
    rounds = competition.rounds.all().order_by('order')
    page_obj = Paginator(rounds, 10).get_page(request.GET.get('page'))
    status_counts = {
        item['status']: item['total']
        for item in rounds.values('status').annotate(total=Count('id'))
    }
    total_weight = rounds.aggregate(total=models.Sum('weight_percentage'))['total'] or Decimal('0')

    context = {
        'competition': competition,
        'rounds': page_obj,
        'page_obj': page_obj,
        'total_rounds': rounds.count(),
        'ongoing_rounds': status_counts.get('ONGOING', 0),
        'completed_rounds': status_counts.get('COMPLETED', 0),
        'total_weight': total_weight,
    }
    return render(request, 'competitions/round_management/manage_rounds.html', context)


@management_required
def create_round(request, competition_id):
    competition = get_object_or_404(Competition, id=competition_id)

    if request.method == 'POST':
        try:
            with transaction.atomic():
                name = request.POST.get('name')
                description = request.POST.get('description')
                order = request.POST.get('order')
                weight_percentage = request.POST.get('weight_percentage')

                total_weight = Round.objects.filter(competition=competition).exclude(status='COMPLETED').aggregate(
                    total=models.Sum('weight_percentage')
                )['total'] or 0

                new_weight = Decimal(weight_percentage)
                if total_weight + new_weight > 100:
                    remaining_weight = 100 - total_weight
                    messages.error(
                        request,
                        f'Total weight percentage cannot exceed 100%. Current total is {total_weight}%. '
                        f'You can add up to {remaining_weight}%.'
                    )
                    return redirect('create_round', competition_id=competition_id)

                round_obj = Round.objects.create(
                    competition=competition,
                    name=name.upper(),
                    description=description.upper(),
                    order=order,
                    weight_percentage=new_weight,
                    status='PENDING'
                )

                criterion_names = request.POST.getlist('criterion_names[]')
                criterion_descriptions = request.POST.getlist('criterion_descriptions[]')
                criterion_max_scores = request.POST.getlist('criterion_max_scores[]')
                criterion_weights = request.POST.getlist('criterion_weights[]')

                for i in range(len(criterion_names)):
                    if criterion_names[i].strip():
                        Criterion.objects.create(
                            round=round_obj,
                            name=criterion_names[i].upper(),
                            description=criterion_descriptions[i].upper() if i < len(criterion_descriptions) and criterion_descriptions[i] else '',
                            max_score=float(criterion_max_scores[i]) if i < len(criterion_max_scores) and criterion_max_scores[i] else 100,
                            weight_percentage=_parse_decimal(
                                criterion_weights[i] if i < len(criterion_weights) else '',
                                Decimal('0'),
                            )
                        )

                messages.success(request, 'Round and criteria created successfully!')
                return redirect('manage_rounds', competition_id=competition_id)

        except Exception as e:
            messages.error(request, f'Error creating round: {str(e)}')
            return redirect('create_round', competition_id=competition_id)

    context = {
        'competition': competition,
    }
    return render(request, 'competitions/round_management/create_round.html', context)


@management_required
def edit_round(request, competition_id, round_id):
    competition = get_object_or_404(Competition, id=competition_id)
    round_obj = get_object_or_404(Round, id=round_id, competition=competition)

    if request.method == 'POST':
        try:
            with transaction.atomic():
                name = request.POST.get('name')
                description = request.POST.get('description')
                order = request.POST.get('order')
                weight_percentage = Decimal(request.POST.get('weight_percentage'))

                other_rounds_weight = Round.objects.filter(competition=competition).exclude(id=round_id).exclude(status='COMPLETED').aggregate(
                    total=models.Sum('weight_percentage')
                )['total'] or 0

                if other_rounds_weight + weight_percentage > 100:
                    remaining_weight = 100 - other_rounds_weight
                    messages.error(
                        request,
                        f'Total weight percentage cannot exceed 100%. Current total (excluding this round) is {other_rounds_weight}%. '
                        f'You can set up to {remaining_weight}%.'
                    )
                    return redirect('edit_round', competition_id=competition_id, round_id=round_id)

                round_obj.name = name.upper()
                round_obj.description = description.upper()
                round_obj.order = order
                round_obj.weight_percentage = weight_percentage
                round_obj.save()

                existing_criteria_ids = set(round_obj.criteria.values_list('id', flat=True))
                updated_criteria_ids = set()

                criterion_names = request.POST.getlist('criterion_names[]')

                if criterion_names:
                    criterion_descriptions = request.POST.getlist('criterion_descriptions[]')
                    criterion_max_scores = request.POST.getlist('criterion_max_scores[]')
                    criterion_ids = request.POST.getlist('criterion_ids[]')
                    criterion_weights = request.POST.getlist('criterion_weights[]')

                    for i in range(len(criterion_names)):
                        if not criterion_names[i].strip():
                            continue

                        weight = _parse_decimal(
                            criterion_weights[i] if i < len(criterion_weights) else '',
                            Decimal('0'),
                        )
                        criterion_id = criterion_ids[i] if i < len(criterion_ids) else None
                        if criterion_id and criterion_id.isdigit():
                            criterion_id = int(criterion_id)
                            if criterion_id in existing_criteria_ids:
                                criterion = Criterion.objects.get(id=criterion_id)
                                criterion.name = criterion_names[i].upper()
                                criterion.description = criterion_descriptions[i].upper() if i < len(criterion_descriptions) and criterion_descriptions[i] else ''
                                criterion.max_score = Decimal(criterion_max_scores[i]) if i < len(criterion_max_scores) and criterion_max_scores[i] else 100
                                criterion.weight_percentage = weight
                                criterion.save()
                                updated_criteria_ids.add(criterion_id)
                        else:
                            criterion = Criterion.objects.create(
                                round=round_obj,
                                name=criterion_names[i].upper(),
                                description=criterion_descriptions[i].upper() if i < len(criterion_descriptions) and criterion_descriptions[i] else '',
                                max_score=Decimal(criterion_max_scores[i]) if i < len(criterion_max_scores) and criterion_max_scores[i] else 100,
                                weight_percentage=weight
                            )
                            updated_criteria_ids.add(criterion.id)

                    criteria_to_delete = existing_criteria_ids - updated_criteria_ids
                    Criterion.objects.filter(id__in=criteria_to_delete).delete()

                messages.success(request, 'Round and criteria updated successfully!')
                return redirect('manage_rounds', competition_id=competition_id)

        except Exception as e:
            messages.error(request, f'Error updating round: {str(e)}')
            return redirect('edit_round', competition_id=competition_id, round_id=round_id)

    context = {
        'competition': competition,
        'round': round_obj,
        'criteria': round_obj.criteria.all(),
    }
    return render(request, 'competitions/round_management/edit_round.html', context)


@management_required
def delete_round(request, competition_id, round_id):
    if request.method != 'POST':
        messages.error(request, 'Invalid request method.')
        return redirect('manage_rounds', competition_id=competition_id)

    try:
        round_obj = get_object_or_404(Round, id=round_id, competition_id=competition_id)

        from scoring.models import Score
        Score.objects.filter(criterion__round=round_obj).delete()
        round_obj.criteria.all().delete()
        round_obj.delete()
        messages.success(request, 'Round and all associated data deleted successfully.')
    except Exception as e:
        messages.error(request, f'Error deleting round: {str(e)}')

    return redirect('manage_rounds', competition_id=competition_id)


@management_required
@require_POST
def toggle_round_status(request, competition_id, round_id):
    with transaction.atomic():
        competition = get_object_or_404(Competition, id=competition_id)
        round_obj = get_object_or_404(
            Round.objects.select_for_update(),
            id=round_id,
            competition=competition,
        )

        status_flow = {
            'PENDING': 'ONGOING',
            'ONGOING': 'COMPLETED',
            'COMPLETED': 'PENDING',
        }
        next_status = status_flow.get(round_obj.status)

        if next_status == 'ONGOING' and competition.rounds.filter(status='ONGOING').exclude(id=round_obj.id).exists():
            messages.error(request, 'Another round is ongoing. Complete it before starting a new round.')
            return redirect('manage_rounds', competition_id=competition_id)

        round_obj.status = next_status
        round_obj.save(update_fields=['status'])

        if next_status == 'COMPLETED':
            calculate_rankings(round_obj)
        elif next_status == 'PENDING':
            # Reopening a completed round invalidates its previously calculated rankings.
            round_obj.results.all().delete()

    action = {
        'ONGOING': 'started',
        'COMPLETED': 'completed',
        'PENDING': 'reopened',
    }[next_status]
    messages.success(request, f"Round '{round_obj.name}' was {action} successfully.")
    return redirect('manage_rounds', competition_id=competition_id)


@management_required
@require_POST
def start_round(request, competition_id, round_id):
    competition = get_object_or_404(Competition, id=competition_id)
    round_obj = get_object_or_404(Round, id=round_id, competition=competition)

    if round_obj.status != 'PENDING':
        messages.error(request, 'Only a pending round can be started.')
        return redirect('manage_rounds', competition_id=competition_id)

    if competition.rounds.filter(status='ONGOING').exists():
        messages.error(request, 'Another round is ongoing. Complete it before starting a new round.')
        return redirect('manage_rounds', competition_id=competition_id)

    round_obj.status = 'ONGOING'
    round_obj.save(update_fields=['status'])

    messages.success(request, f"Round '{round_obj.name}' was started successfully.")
    return redirect('manage_rounds', competition_id=competition_id)


@management_required
@require_POST
def complete_round(request, competition_id, round_id):
    competition = get_object_or_404(Competition, id=competition_id)
    round_obj = get_object_or_404(Round, id=round_id, competition=competition)

    if round_obj.status != 'ONGOING':
        messages.error(request, 'Only an ongoing round can be completed.')
        return redirect('manage_rounds', competition_id=competition_id)

    round_obj.status = 'COMPLETED'
    round_obj.save(update_fields=['status'])
    calculate_rankings(round_obj)

    messages.success(request, f"Round '{round_obj.name}' was completed successfully.")
    return redirect('manage_rounds', competition_id=competition_id)
