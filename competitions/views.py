import re
from decimal import Decimal, InvalidOperation
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction, models
from django.core.paginator import Paginator
from django.http import JsonResponse
from django.urls import reverse
from django.views.decorators.http import require_POST

from .models import (
    Competition, Round, Criterion, CulturalMainType, CulturalSubType,
    cultural_subtype_groups, cultural_subtype_labels,
)
from scoring.services import calculate_rankings
from django.db.models import Count, Exists, OuterRef, Q
from django.db.models.functions import Lower
from sports.models import SportsEvent
from accounts.access import MANAGEMENT_ROLES, get_user_role, management_required


def _competition_list_url(category='sports'):
    """Return the list URL for a category, keeping sports as the default."""
    url = reverse('competition_list')
    if str(category).lower() == 'cultural':
        return f'{url}?category=cultural'
    return url


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


def _validate_category_fields(post):
    """Sports and Socio Cultural competitions must be declared explicitly so
    the match board, cultural hub and reports classify them correctly.
    Returns (kind, cultural_event_type, errors); nothing is saved when the
    selection is invalid."""
    kind = (post.get('kind') or '').strip()
    event_type = (post.get('cultural_event_type') or '').strip()
    errors = []

    if kind not in Competition.Kind.values:
        errors.append('Select the competition category: Sports or Socio Cultural.')
    elif kind == Competition.Kind.CULTURAL:
        if (
            event_type not in Competition.CulturalEventType.values
            and not CulturalSubType.objects.filter(slug=event_type).exists()
        ):
            errors.append(
                'Select a Socio Cultural sub-type (for example dancing, singing, or literary arts).'
            )
    else:
        # Sports (and legacy Mixed) competitions never carry a cultural sub-type.
        event_type = ''

    return kind, event_type, errors


def _subtype_form_context(kind, selected):
    """Shared context for the cultural sub-type field on create/edit forms."""
    return {
        'subtype_groups': cultural_subtype_groups(),
        'selected_subtype': selected or '',
        'is_cultural': kind == Competition.Kind.CULTURAL,
        'can_manage_subtypes': True,
    }


def _medal_points(post):
    """Fields shared by create/edit competition forms for the medal tally."""
    return {
        'gold_points': _parse_decimal(post.get('gold_points'), Decimal('10')),
        'silver_points': _parse_decimal(post.get('silver_points'), Decimal('5')),
        'bronze_points': _parse_decimal(post.get('bronze_points'), Decimal('3')),
    }


def _competition_search_q(category, term):
    """Case insensitive search filter for the list page.

    The database collation compares strings case sensitively, so the term is
    matched against lowered columns instead of trusting LIKE's collation. The
    competition name and description are always searched; cultural competitions
    also match their event type and sports competitions their events, sport and
    venue names. Sports matches use a subquery so a competition is never
    duplicated or dropped by the event join.
    """
    needle = term.lower()
    query = (
        Q(search_name__contains=needle)
        | Q(search_description__contains=needle)
    )
    if category == 'cultural':
        return query | Q(search_event_type__contains=needle)

    events = (
        SportsEvent.objects
        .annotate(
            search_event=Lower('name'),
            search_sport=Lower('sport_type__name'),
            search_venue=Lower('venue__name'),
        )
        .filter(
            Q(search_event__contains=needle)
            | Q(search_sport__contains=needle)
            | Q(search_venue__contains=needle),
            competition=OuterRef('pk'),
        )
    )
    return query | Exists(events)


def _cultural_subcategories(queryset):
    """Cultural sub-type chips built from the competitions currently in range."""
    labels = cultural_subtype_labels()
    rows = (
        queryset
        .exclude(cultural_event_type='')
        .values('cultural_event_type')
        .annotate(n=Count('id'))
        .order_by('cultural_event_type')
    )
    return [
        {
            'value': row['cultural_event_type'],
            'label': labels.get(
                row['cultural_event_type'],
                row['cultural_event_type'].replace('_', ' ').title(),
            ),
            'count': row['n'],
        }
        for row in rows
    ]


def _sports_subcategories(queryset):
    """Sport-type chips built from the events attached to the competitions in
    range; a competition running two sports is counted under both."""
    rows = (
        queryset
        .filter(sport_events__isnull=False)
        .values('sport_events__sport_type_id', 'sport_events__sport_type__name')
        .annotate(n=Count('id', distinct=True))
        .order_by('sport_events__sport_type__name')
    )
    return [
        {
            'value': str(row['sport_events__sport_type_id']),
            'label': row['sport_events__sport_type__name'],
            'count': row['n'],
        }
        for row in rows
    ]


@login_required
def competition_list(request):
    # Sports and Socio Cultural competitions live in separate tabs. Sports is
    # the default so the two categories are never mixed on one page.
    category = (request.GET.get('category') or 'sports').strip().lower()
    if category not in ('sports', 'cultural'):
        category = 'sports'
    is_cultural = category == 'cultural'

    competitions = Competition.objects.all()
    if get_user_role(request.user) not in MANAGEMENT_ROLES:
        competitions = competitions.filter(status__in=['ACTIVE', 'COMPLETED'])

    counts = competitions.aggregate(
        sports=Count('id', filter=~Q(kind=Competition.Kind.CULTURAL)),
        cultural=Count('id', filter=Q(kind=Competition.Kind.CULTURAL)),
    )

    if is_cultural:
        competitions = competitions.filter(kind=Competition.Kind.CULTURAL)
    else:
        competitions = competitions.exclude(kind=Competition.Kind.CULTURAL)

    # The search is applied before the chips are counted so every counter
    # describes what the user would actually get when clicking it.
    query = (request.GET.get('q') or '').strip()
    if query:
        competitions = competitions.annotate(
            search_name=Lower('name'),
            search_description=Lower('description'),
            search_event_type=Lower('cultural_event_type'),
        ).filter(_competition_search_q(category, query))

    subcategories = (
        _cultural_subcategories(competitions)
        if is_cultural else _sports_subcategories(competitions)
    )
    all_count = competitions.count()

    # Only accept a sub-category that exists in the current range.
    sub = (request.GET.get('sub') or '').strip()
    selected_sub = next(
        (item['value'] for item in subcategories if item['value'] == sub), ''
    )
    if selected_sub:
        if is_cultural:
            competitions = competitions.filter(cultural_event_type=selected_sub)
        else:
            competitions = competitions.filter(
                sport_events__sport_type_id=int(selected_sub)
            )

    competitions = competitions.order_by('-id').annotate(
        rounds_count=Count('rounds', distinct=True),
        criteria_count=Count('rounds__criteria', distinct=True),
    )
    page_obj = Paginator(competitions, 9).get_page(request.GET.get('page'))
    return render(request, 'competitions/competition_list.html', {
        'page_obj': page_obj,
        'category': category,
        'sports_count': counts['sports'] or 0,
        'cultural_count': counts['cultural'] or 0,
        'subcategories': subcategories,
        'selected_sub': selected_sub,
        'selected_sub_label': next(
            (item['label'] for item in subcategories if item['value'] == selected_sub), ''
        ),
        'query': query,
        'all_count': all_count,
        'result_count': page_obj.paginator.count,
        'is_filtered': bool(query) or bool(selected_sub),
        'subtype_groups': cultural_subtype_groups(),
        'can_manage_subtypes': get_user_role(request.user) in MANAGEMENT_ROLES,
    })


@management_required
def socio_cultural_management(request):
    """Home for staff to run socio-cultural competitions (dance, singing,
    pageants, quiz bees and the like) apart from sports brackets. Only
    competitions flagged as cultural appear here; sports stay in the Sports
    hub and match board."""
    competitions = (
        Competition.objects
        .filter(kind=Competition.Kind.CULTURAL)
        .annotate(
            rounds_count=Count('rounds', distinct=True),
            criteria_count=Count('rounds__criteria', distinct=True),
            participant_count=Count('participants', distinct=True),
        )
        .order_by('-start_date', '-id')
    )

    # Event-type chips act as a quick filter without leaving the page.
    labels = cultural_subtype_labels()
    selected_type = request.GET.get('type', '')
    if selected_type not in labels:
        selected_type = ''
    if selected_type:
        competitions = competitions.filter(cultural_event_type=selected_type)

    type_counts = [
        {
            'value': row['cultural_event_type'],
            'label': labels.get(
                row['cultural_event_type'],
                row['cultural_event_type'].replace('_', ' ').title(),
            ),
            'count': row['n'],
        }
        for row in (
            Competition.objects
            .filter(kind=Competition.Kind.CULTURAL)
            .exclude(cultural_event_type='')
            .values('cultural_event_type')
            .annotate(n=Count('id'))
            .order_by('cultural_event_type')
        )
    ]

    rows = list(competitions)
    stats = {
        'competitions': len(rows),
        'active': sum(1 for c in rows if c.status == 'ACTIVE'),
        'completed': sum(1 for c in rows if c.status == 'COMPLETED'),
        'rounds': sum(c.rounds_count for c in rows),
        'participants': sum(c.participant_count for c in rows),
    }
    return render(request, 'competitions/socio_cultural_management.html', {
        'cultural_competitions': rows,
        'stats': stats,
        'type_counts': type_counts,
        'selected_type': selected_type,
    })


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
        kind, event_type, category_errors = _validate_category_fields(request.POST)
        if category_errors:
            # Re-render with the submitted values so staff can fix the choice.
            return render(request, 'competitions/create_competition.html', {
                'form_data': request.POST,
                'category_errors': category_errors,
                **_subtype_form_context(kind, request.POST.get('cultural_event_type')),
            })
        try:
            with transaction.atomic():
                competition = Competition.objects.create(
                    name=request.POST.get('name').upper(),
                    description=request.POST.get('description').upper(),
                    start_date=request.POST.get('start_date'),
                    end_date=request.POST.get('end_date'),
                    status=request.POST.get('status'),
                    created_by=request.user,
                    kind=kind,
                    cultural_event_type=event_type,
                    **_medal_points(request.POST)
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
            return redirect(_competition_list_url(kind))
        except Exception as e:
            messages.error(request, f'Error creating competition: {str(e)}')
            return render(request, 'competitions/create_competition.html', {
                'form_data': request.POST,
                **_subtype_form_context(kind, event_type),
            })

    return render(request, 'competitions/create_competition.html', _subtype_form_context('', ''))


@management_required
def edit_competition(request, competition_id):
    competition = get_object_or_404(Competition, id=competition_id)

    if request.method == 'POST':
        kind, event_type, category_errors = _validate_category_fields(request.POST)
        if category_errors:
            # Echo the submitted values (unsaved) so staff can fix the choice.
            competition.name = (request.POST.get('title') or competition.name).upper()
            competition.description = (request.POST.get('description') or '').upper() or competition.description
            competition.kind = request.POST.get('kind') or competition.kind
            competition.cultural_event_type = request.POST.get('cultural_event_type') or competition.cultural_event_type
            return render(request, 'competitions/edit_competition.html', {
                'competition': competition,
                'category_errors': category_errors,
                **_subtype_form_context(
                    request.POST.get('kind'), request.POST.get('cultural_event_type'),
                ),
            })

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
        competition.kind = kind
        competition.cultural_event_type = event_type
        for key, value in _medal_points(request.POST).items():
            setattr(competition, key, value)
        competition.save()

        messages.success(request, 'Competition updated successfully!')
        return redirect('competition_detail', competition_id=competition.id)

    return render(request, 'competitions/edit_competition.html', {
        'competition': competition,
        **_subtype_form_context(competition.kind, competition.cultural_event_type),
    })


def _subtype_slug(name):
    return re.sub(r'[^A-Z0-9]+', '_', name.upper()).strip('_')[:30].strip('_')


@management_required
@require_POST
def add_cultural_subtype(request):
    """Create a cultural sub-type (and optionally its main group) from the
    competition form so staff are not limited to the seeded list."""
    name = (request.POST.get('name') or '').strip()
    main_id = (request.POST.get('main_type') or '').strip()
    new_main_name = (request.POST.get('new_main_type') or '').strip()

    if not name:
        return JsonResponse({'error': 'Enter a sub-type name.'}, status=400)
    if len(name) > 100:
        return JsonResponse({'error': 'Sub-type name is too long (max 100 characters).'}, status=400)

    slug = _subtype_slug(name)
    if not slug:
        return JsonResponse({'error': 'Use letters or numbers in the sub-type name.'}, status=400)

    # LIKE is case sensitive in this database, so match names through Lower().
    existing = (
        CulturalSubType.objects
        .annotate(lower_name=Lower('name'))
        .filter(Q(lower_name=name.lower()) | Q(slug=slug))
        .select_related('main_type')
        .first()
    )
    if existing:
        return JsonResponse({
            'id': existing.id, 'slug': existing.slug, 'name': existing.name,
            'main_id': existing.main_type_id, 'main_type': existing.main_type.name,
        })

    if main_id == '__new__':
        if not new_main_name:
            return JsonResponse({'error': 'Enter a name for the new main group.'}, status=400)
        if len(new_main_name) > 100:
            return JsonResponse({'error': 'Main group name is too long (max 100 characters).'}, status=400)
        main = (
            CulturalMainType.objects
            .annotate(lower_name=Lower('name'))
            .filter(lower_name=new_main_name.lower())
            .first()
        )
        if main is None:
            main = CulturalMainType.objects.create(name=new_main_name)
    else:
        main = CulturalMainType.objects.filter(id=main_id).first() if main_id.isdigit() else None
        if main is None:
            return JsonResponse({'error': 'Pick a main group or add a new one.'}, status=400)

    subtype = CulturalSubType.objects.create(main_type=main, name=name, slug=slug)
    return JsonResponse({
        'id': subtype.id, 'slug': subtype.slug, 'name': subtype.name,
        'main_id': main.id, 'main_type': main.name,
    })


@management_required
@require_POST
def edit_cultural_subtype(request):
    """Rename a sub-type or move it to another main group. The slug never
    changes so competitions already using it keep their classification."""
    subtype_id = (request.POST.get('id') or '').strip()
    subtype = CulturalSubType.objects.filter(id=subtype_id).first() if subtype_id.isdigit() else None
    if subtype is None:
        return JsonResponse({'error': 'Sub-type not found.'}, status=404)

    name = (request.POST.get('name') or '').strip()
    if not name:
        return JsonResponse({'error': 'Enter a sub-type name.'}, status=400)
    if len(name) > 100:
        return JsonResponse({'error': 'Sub-type name is too long (max 100 characters).'}, status=400)

    main_id = (request.POST.get('main_type') or '').strip()
    main = CulturalMainType.objects.filter(id=main_id).first() if main_id.isdigit() else None
    if main is None:
        return JsonResponse({'error': 'Pick a main group.'}, status=400)

    # LIKE is case sensitive in this database, so match names through Lower().
    clash = (
        CulturalSubType.objects
        .annotate(lower_name=Lower('name'))
        .filter(Q(lower_name=name.lower()) | Q(slug=_subtype_slug(name)))
        .exclude(id=subtype.id)
        .exists()
    )
    if clash:
        return JsonResponse({'error': 'A sub-type with this name already exists.'}, status=400)

    subtype.name = name
    subtype.main_type = main
    subtype.save()
    return JsonResponse({
        'id': subtype.id, 'slug': subtype.slug, 'name': subtype.name,
        'main_id': main.id, 'main_type': main.name,
    })


@management_required
@require_POST
def delete_cultural_subtype(request):
    subtype_id = (request.POST.get('id') or '').strip()
    subtype = CulturalSubType.objects.filter(id=subtype_id).first() if subtype_id.isdigit() else None
    if subtype is None:
        return JsonResponse({'error': 'Sub-type not found.'}, status=404)

    used = Competition.objects.filter(cultural_event_type=subtype.slug).count()
    if used:
        return JsonResponse({
            'error': f'Cannot delete "{subtype.name}": {used} competition(s) still use it. '
                     'Edit those competitions first.',
        }, status=400)

    slug = subtype.slug
    subtype.delete()
    return JsonResponse({'deleted': True, 'id': int(subtype_id), 'slug': slug})


@management_required
@require_POST
def edit_cultural_main_type(request):
    main_id = (request.POST.get('id') or '').strip()
    main = CulturalMainType.objects.filter(id=main_id).first() if main_id.isdigit() else None
    if main is None:
        return JsonResponse({'error': 'Main group not found.'}, status=404)

    name = (request.POST.get('name') or '').strip()
    if not name:
        return JsonResponse({'error': 'Enter a main group name.'}, status=400)
    if len(name) > 100:
        return JsonResponse({'error': 'Main group name is too long (max 100 characters).'}, status=400)

    clash = (
        CulturalMainType.objects
        .annotate(lower_name=Lower('name'))
        .filter(lower_name=name.lower())
        .exclude(id=main.id)
        .exists()
    )
    if clash:
        return JsonResponse({'error': 'A main group with this name already exists.'}, status=400)

    main.name = name
    main.save()
    return JsonResponse({'id': main.id, 'name': main.name})


@management_required
@require_POST
def delete_cultural_main_type(request):
    main_id = (request.POST.get('id') or '').strip()
    main = CulturalMainType.objects.filter(id=main_id).first() if main_id.isdigit() else None
    if main is None:
        return JsonResponse({'error': 'Main group not found.'}, status=404)

    if main.subtypes.exists():
        return JsonResponse({
            'error': f'Cannot delete "{main.name}": it still has sub-types. '
                     'Move or delete them first.',
        }, status=400)

    main.delete()
    return JsonResponse({'deleted': True, 'id': int(main_id)})


@management_required
def delete_competition(request, competition_id):
    if request.method == 'POST':
        competition = get_object_or_404(Competition, id=competition_id)
        category = competition.kind
        competition.delete()
        messages.success(request, 'Competition deleted successfully.')
        return redirect(_competition_list_url(category))
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
        return redirect(_competition_list_url(competition.kind))


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
