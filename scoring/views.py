import os
import re
from io import BytesIO
from decimal import Decimal, InvalidOperation
from collections import OrderedDict
from datetime import datetime

from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse, HttpResponseBadRequest, JsonResponse
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction, models
from django.conf import settings

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch, cm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image, HRFlowable
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

from competitions.models import Competition, Round, Criterion
from participants.models import Participant
from judges.models import Judge, JudgeAssignment
from .models import Score, CompetitionResult
from .services import (
    calculate_participant_total_score,
    calculate_rankings,
    build_round_results,
    build_overall_standings,
)


def _parse_score_value(raw_value, maximum):
    """Parse and validate a score without introducing float rounding."""
    if raw_value in (None, ''):
        raise ValueError('Every criterion must have a score.')

    try:
        value = Decimal(raw_value)
    except (InvalidOperation, TypeError):
        raise ValueError('Score must be a valid number.') from None

    if not value.is_finite() or value < 0 or value > maximum:
        raise ValueError(f'Score must be between 0 and {maximum}.')
    if value.as_tuple().exponent < -2:
        raise ValueError('Score can have at most two decimal places.')

    return value.quantize(Decimal('0.01'))


def _is_assigned_to_round(judge, round_obj):
    return JudgeAssignment.objects.filter(
        judge=judge,
        competition=round_obj.competition,
        rounds=round_obj,
        status='ACTIVE',
    ).exists()


@login_required
def scoring_panel(request, round_id):
    round_obj = get_object_or_404(Round, id=round_id)
    judge = get_object_or_404(Judge, user=request.user)

    if not _is_assigned_to_round(judge, round_obj):
        messages.error(request, 'You are not assigned to judge this round.')
        return redirect('judge_dashboard')

    if round_obj.status != 'ONGOING':
        messages.warning(request, 'Scoring is only available for ongoing rounds.')
        return redirect('judge_dashboard')

    if request.method == 'POST':
        with transaction.atomic():
            participant_id = request.POST.get('participant_id')
            participant = get_object_or_404(
                Participant.objects.filter(
                    participantcompetition__competition=round_obj.competition,
                ).distinct(),
                id=participant_id,
            )

            if Score.objects.filter(
                participant=participant,
                criterion__round=round_obj,
                judge=judge,
                status='SUBMITTED',
            ).exists():
                messages.warning(request, 'These scores have already been submitted and are locked.')
                return redirect('scoring_panel', round_id=round_id)

            criteria = list(round_obj.criteria.all())
            parsed_scores = []
            try:
                for criterion in criteria:
                    parsed_scores.append((
                        criterion,
                        _parse_score_value(
                            request.POST.get(f'score_{participant_id}_{criterion.id}'),
                            criterion.max_score,
                        ),
                        request.POST.get(f'remarks_{participant_id}_{criterion.id}', ''),
                    ))
            except ValueError as error:
                messages.error(request, str(error))
                return redirect('scoring_panel', round_id=round_id)

            for criterion, score_value, remarks in parsed_scores:
                Score.objects.update_or_create(
                    participant=participant,
                    criterion=criterion,
                    judge=judge,
                    defaults={
                        'score': score_value,
                        'remarks': remarks,
                        'status': 'SUBMITTED'
                    }
                )

            total_score = calculate_participant_total_score(
                participant,
                round_obj,
                include_draft=False,
            )

            CompetitionResult.objects.update_or_create(
                competition=round_obj.competition,
                participant=participant,
                round=round_obj,
                defaults={
                    'total_score': total_score,
                    'rank': 0
                }
            )

            calculate_rankings(round_obj)
            messages.success(request, 'Scores submitted successfully!')
            return redirect('scoring_panel', round_id=round_id)

    submitted_scores = set(Score.objects.filter(
        judge=judge,
        criterion__round=round_obj,
        status='SUBMITTED'
    ).values_list('participant_id', flat=True).distinct())

    participants = Participant.objects.filter(
        participantcompetition__competition=round_obj.competition
    ).annotate(
        number=models.F('participantcompetition__number'),
    ).order_by('number')

    for participant in participants:
        participant.scores_submitted = participant.id in submitted_scores

    criteria = list(round_obj.criteria.all())

    existing_scores = Score.objects.filter(
        judge=judge,
        criterion__round=round_obj
    ).select_related('participant', 'criterion')

    score_lookup = {}
    remarks_lookup = {}
    for score in existing_scores:
        if score.participant_id not in score_lookup:
            score_lookup[score.participant_id] = {}
            remarks_lookup[score.participant_id] = {}
        score_lookup[score.participant_id][score.criterion_id] = score.score
        remarks_lookup[score.participant_id][score.criterion_id] = score.remarks

    total_scores = {
        participant.id: sum(
            score_lookup.get(participant.id, {}).values(),
            Decimal('0'),
        ).quantize(Decimal('0.01'))
        for participant in participants
    }

    context = {
        'round': round_obj,
        'participants': participants,
        'criteria': criteria,
        'existing_scores': score_lookup,
        'existing_remarks': remarks_lookup,
        'total_scores': total_scores,
        'judge': judge,
        'total_max_score': sum(
            (criterion.max_score for criterion in criteria),
            Decimal('0'),
        ),
    }

    return render(request, 'scoring/judge/scoring_panel.html', context)


@login_required
def update_score(request, round_id):
    if not request.headers.get('HX-Request'):
        return HttpResponseBadRequest("Not an HTMX request")

    if request.method != 'POST':
        return HttpResponseBadRequest('POST required')

    judge = get_object_or_404(Judge, user=request.user)
    round_obj = get_object_or_404(Round, id=round_id)
    if round_obj.status != 'ONGOING' or not _is_assigned_to_round(judge, round_obj):
        return HttpResponse('You are not allowed to score this round.', status=403)

    score_field = None
    score_match = None
    for key in request.POST.keys():
        match = re.fullmatch(r'score(?:_input)?_(\d+)_(\d+)', key)
        if match:
            score_field = key
            score_match = match
            break
    if score_field is None:
        return HttpResponseBadRequest('No score field found')

    participant_id, criterion_id = score_match.groups()
    participant = get_object_or_404(
        Participant.objects.filter(
            participantcompetition__competition=round_obj.competition,
        ).distinct(),
        id=participant_id,
    )
    criterion = get_object_or_404(Criterion, id=criterion_id, round=round_obj)

    try:
        score_value = _parse_score_value(
            request.POST.get(score_field),
            criterion.max_score,
        )
    except ValueError as error:
        return HttpResponseBadRequest(str(error))

    existing_score = Score.objects.filter(
        participant=participant,
        criterion=criterion,
        judge=judge,
    ).first()
    if existing_score and existing_score.status == 'SUBMITTED':
        return HttpResponse('Submitted scores are locked.', status=409)

    Score.objects.update_or_create(
        participant=participant,
        criterion=criterion,
        judge=judge,
        defaults={
            'score': score_value,
            'status': 'DRAFT',
        },
    )

    total_score = calculate_participant_total_score(
        participant,
        round_obj,
        include_draft=True,
        judge=judge,
    )

    return HttpResponse(f"{total_score:.1f}")


@login_required
def competition_results_detail(request, competition_id):
    competition = get_object_or_404(Competition.objects.prefetch_related(
        'rounds',
        'rounds__criteria',
        'rounds__results',
        'rounds__results__participant',
        'participants',
        'judge_assignments',
        'judge_assignments__judge'
    ), id=competition_id)

    rounds = list(build_round_results(competition))
    overall_standings = build_overall_standings(competition)

    context = {
        'competition': competition,
        'rounds': rounds,
        'overall_standings': overall_standings,
    }

    return render(request, 'scoring/competition_results_detail.html', context)


@login_required
def results_print(request, competition_id):
    competition = get_object_or_404(Competition.objects.prefetch_related(
        'rounds',
        'rounds__criteria',
        'rounds__results',
        'rounds__results__participant',
        'participants',
        'judge_assignments',
        'judge_assignments__judge',
        'judge_assignments__rounds',
    ), id=competition_id)

    rounds = list(build_round_results(competition))
    overall_standings = build_overall_standings(competition)

    selected_view = request.GET.get('view', 'overall')
    selected_round = None
    if selected_view.startswith('round-'):
        try:
            selected_round_id = int(selected_view.removeprefix('round-'))
        except ValueError:
            selected_view = 'overall'
        else:
            selected_round = next(
                (round_obj for round_obj in rounds if round_obj.id == selected_round_id),
                None,
            )
            if selected_round is None:
                selected_view = 'overall'
    elif selected_view != 'overall':
        selected_view = 'overall'

    for round_obj in rounds:
        round_obj.round_judges = Judge.objects.filter(
            assignments__competition=competition,
            assignments__rounds=round_obj,
            assignments__status='ACTIVE',
        ).select_related('user').distinct()

    final_judges = Judge.objects.filter(
        assignments__competition=competition,
        assignments__status='ACTIVE',
    ).select_related('user').distinct()

    context = {
        'competition': competition,
        'rounds': rounds,
        'overall_standings': overall_standings,
        'final_judges': final_judges,
        'selected_view': selected_view,
        'selected_round': selected_round,
    }

    return render(request, 'scoring/print_results.html', context)


@login_required
def results_reveal(request, competition_id):
    competition = get_object_or_404(Competition.objects.prefetch_related(
        'rounds',
        'participants',
        'judge_assignments__judge__user',
        'results'
    ), id=competition_id)

    results = CompetitionResult.objects.filter(
        competition=competition,
        round=competition.rounds.last()
    ).select_related('participant').order_by('rank')

    judges = Judge.objects.filter(
        assignments__competition=competition,
        assignments__status='ACTIVE'
    ).select_related('user').distinct()

    context = {
        'competition': competition,
        'results': results,
        'first_place': results.filter(rank=1).first(),
        'second_place': results.filter(rank=2).first(),
        'third_place': results.filter(rank=3).first(),
        'judges': judges,
        'total_participants': results.count(),
        'total_judges': judges.count(),
    }

    return render(request, 'scoring/results_reveal.html', context)


@login_required
def toggle_results_visibility(request, competition_id):
    if request.method == 'POST' and request.user.is_superuser:
        competition = get_object_or_404(Competition, id=competition_id)
        show_results = request.POST.get('show_results') == 'true'

        competition.show_results = show_results
        competition.save()

        return JsonResponse({'status': 'success'})
    return JsonResponse({'status': 'error'}, status=403)


@login_required
def round_results(request, competition_id, round_id):
    competition = get_object_or_404(Competition, id=competition_id)
    round_obj = get_object_or_404(Round, id=round_id, competition=competition)

    if round_obj.status != 'COMPLETED':
        messages.error(request, 'Results are only available for completed rounds.')
        return redirect('manage_rounds', competition_id=competition_id)

    criteria = round_obj.criteria.all()

    all_results = CompetitionResult.objects.filter(
        round=round_obj
    ).select_related('participant').order_by('rank')

    results = Paginator(all_results, 10).get_page(request.GET.get('page'))

    for result in results:
        criterion_scores = {}
        for criterion in criteria:
            avg_score = Score.objects.filter(
                participant=result.participant,
                criterion=criterion,
                status='SUBMITTED'
            ).aggregate(avg=models.Avg('score'))['avg'] or 0
            criterion_scores[criterion.id] = avg_score
        result.criterion_scores = criterion_scores

    scores = [result.total_score for result in all_results]
    statistics = {
        'highest_score': max(scores) if scores else 0,
        'average_score': sum(scores) / len(scores) if scores else 0,
        'lowest_score': min(scores) if scores else 0,
        'total_participants': len(scores)
    }

    context = {
        'competition': competition,
        'round': round_obj,
        'criteria': criteria,
        'results': results,
        'page_obj': results,
        'statistics': statistics
    }

    return render(request, 'scoring/round_results.html', context)


@login_required
def generate_results_pdf(request, competition_id):
    competition = get_object_or_404(Competition, id=competition_id)
    rounds = competition.rounds.all().order_by('order')

    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{competition.name}_Official_Results.pdf"'

    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=landscape(A4),
        rightMargin=35,
        leftMargin=35,
        topMargin=35,
        bottomMargin=35
    )

    elements = []

    styles = getSampleStyleSheet()

    primary_color = colors.HexColor('#1e3a8a')
    secondary_color = colors.HexColor('#1e40af')
    accent_color = colors.HexColor('#3b82f6')
    background_stripe = colors.HexColor('#f8fafc')
    text_color = colors.HexColor('#1e293b')
    header_bg = colors.HexColor('#1e3a8a')

    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=24,
        spaceAfter=20,
        alignment=1,
        textColor=primary_color,
        fontName='Helvetica-Bold',
        leading=32
    )

    heading_style = ParagraphStyle(
        'CustomHeading',
        parent=styles['Heading2'],
        fontSize=16,
        spaceAfter=16,
        spaceBefore=20,
        textColor=secondary_color,
        fontName='Helvetica-Bold',
        leading=20
    )

    elements.append(Spacer(1, 20))
    elements.append(Paragraph("OFFICIAL RESULTS", ParagraphStyle(
        'OfficialHeader',
        parent=styles['Normal'],
        fontSize=14,
        textColor=text_color,
        alignment=1,
        fontName='Helvetica-Bold'
    )))
    elements.append(Spacer(1, 10))
    elements.append(Paragraph(competition.name.upper(), title_style))
    elements.append(HRFlowable(
        width="100%",
        thickness=1,
        color=accent_color,
        spaceBefore=10,
        spaceAfter=20,
        hAlign='CENTER'
    ))

    info_data = [
        ["Competition Date:", datetime.now().strftime("%B %d, %Y")],
        ["Number of Rounds:", str(rounds.count())],
        ["Total Participants:", str(competition.participants.count())]
    ]

    info_table = Table(info_data, colWidths=[180, 300])
    info_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 11),
        ('TEXTCOLOR', (0, 0), (0, -1), secondary_color),
        ('TEXTCOLOR', (1, 0), (1, -1), text_color),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
        ('TOPPADDING', (0, 0), (-1, -1), 12),
        ('BACKGROUND', (0, 0), (-1, -1), background_stripe),
        ('GRID', (0, 0), (-1, -1), 0.5, accent_color),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('LEFTPADDING', (0, 0), (-1, -1), 16),
    ]))
    elements.append(info_table)
    elements.append(Spacer(1, 30))

    for round_obj in rounds:
        round_header = Table([[
            Paragraph(f"Round {round_obj.order}: {round_obj.name}", heading_style),
            Paragraph(f"Weight: {round_obj.weight_percentage}%",
                      ParagraphStyle('RoundInfo',
                                    parent=styles['Normal'],
                                    textColor=text_color,
                                    fontSize=11,
                                    alignment=2))
        ]], colWidths=[400, 100])
        round_header.setStyle(TableStyle([
            ('ALIGN', (0, 0), (0, 0), 'LEFT'),
            ('ALIGN', (1, 0), (1, 0), 'RIGHT'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ]))
        elements.append(round_header)
        elements.append(Spacer(1, 10))

        results = CompetitionResult.objects.filter(
            round=round_obj
        ).select_related('participant').order_by('rank')

        if results:
            judge_scores = Score.objects.filter(criterion__round=round_obj).select_related('judge')
            judges = list({score.judge for score in judge_scores})

            headers = ['Rank', 'Participant']
            headers.extend([f'Judge {j.user.get_full_name()}' for j in judges])
            headers.extend(['Total', 'Weighted'])

            table_data = [headers]

            for result in results:
                row = [str(result.rank), result.participant.name]

                for judge in judges:
                    judge_scores = Score.objects.filter(
                        criterion__round=round_obj,
                        judge=judge,
                        participant=result.participant
                    ).aggregate(avg_score=models.Avg('score'))
                    row.append(f"{judge_scores['avg_score']:.1f}" if judge_scores['avg_score'] else "-")

                weighted_score = result.total_score * (round_obj.weight_percentage / 100)
                row.extend([f"{result.total_score:.1f}", f"{weighted_score:.1f}"])
                table_data.append(row)

            col_widths = [50]
            col_widths.append(200)
            col_widths.extend([150] * len(judges))
            col_widths.extend([80, 80])

            table = Table(table_data, colWidths=col_widths)
            table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), header_bg),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 11),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('TOPPADDING', (0, 0), (-1, 0), 12),
                ('ALIGN', (0, 0), (-1, 0), 'CENTER'),

                ('BACKGROUND', (0, 1), (-1, -1), colors.white),
                ('TEXTCOLOR', (0, 1), (-1, -1), text_color),
                ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 1), (-1, -1), 10),
                ('BOTTOMPADDING', (0, 1), (-1, -1), 10),
                ('TOPPADDING', (0, 1), (-1, -1), 10),

                ('ALIGN', (0, 0), (0, -1), 'CENTER'),
                ('ALIGN', (1, 0), (1, -1), 'LEFT'),
                ('ALIGN', (2, 0), (-1, -1), 'CENTER'),

                ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e2e8f0')),
                ('BOX', (0, 0), (-1, -1), 1, header_bg),

                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, background_stripe]),

                ('LEFTPADDING', (0, 0), (-1, -1), 12),
                ('RIGHTPADDING', (0, 0), (-1, -1), 12),
            ]))
            elements.append(table)
            elements.append(Spacer(1, 25))

    elements.append(Paragraph("Final Rankings", heading_style))
    elements.append(Spacer(1, 15))

    final_rankings = []
    for participant in competition.participants.all():
        total_score = 0
        for round_obj in rounds:
            result = CompetitionResult.objects.filter(
                round=round_obj,
                participant=participant
            ).first()
            if result:
                total_score += result.total_score * (round_obj.weight_percentage / 100)
        final_rankings.append((participant, total_score))

    final_rankings.sort(key=lambda x: x[1], reverse=True)

    def get_performance_style(score):
        if score >= 95:
            return ('Gold Medal', colors.HexColor('#1e3a8a'))
        elif score >= 85:
            return ('Silver Medal', colors.HexColor('#1e40af'))
        elif score >= 75:
            return ('Bronze Medal', colors.HexColor('#2563eb'))
        elif score >= 65:
            return ('Honorable Mention', colors.HexColor('#3b82f6'))
        return ('Participant', colors.HexColor('#60a5fa'))

    final_table_data = [['Rank', 'Participant', 'Total Score', 'Classification']]

    for idx, (participant, total_score) in enumerate(final_rankings, 1):
        performance, color = get_performance_style(total_score)
        final_table_data.append([
            str(idx),
            participant.name,
            f"{total_score:.1f}",
            Paragraph(performance, ParagraphStyle(
                'PerformanceBadge',
                parent=styles['Normal'],
                fontSize=10,
                textColor=colors.white,
                backColor=color,
                alignment=1,
                borderPadding=6,
                leading=12
            ))
        ])

    final_table = Table(final_table_data, colWidths=[60, 250, 120, 180])
    final_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), header_bg),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 11),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('TOPPADDING', (0, 0), (-1, 0), 12),

        ('BACKGROUND', (0, 1), (-1, -1), colors.white),
        ('TEXTCOLOR', (0, 1), (-1, -1), text_color),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 1), (-1, -1), 10),
        ('TOPPADDING', (0, 1), (-1, -1), 10),

        ('ALIGN', (0, 0), (0, -1), 'CENTER'),
        ('ALIGN', (1, 0), (1, -1), 'LEFT'),
        ('ALIGN', (2, 0), (2, -1), 'CENTER'),
        ('ALIGN', (3, 0), (3, -1), 'CENTER'),

        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e2e8f0')),
        ('BOX', (0, 0), (-1, -1), 1, header_bg),

        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, background_stripe]),

        ('LEFTPADDING', (0, 0), (-1, -1), 12),
        ('RIGHTPADDING', (0, 0), (-1, -1), 12),
    ]))

    elements.append(final_table)
    elements.append(Spacer(1, 25))

    elements.append(Spacer(1, 40))
    elements.append(Paragraph("CERTIFICATION", heading_style))
    elements.append(Spacer(1, 15))

    judge_assignments = JudgeAssignment.objects.filter(
        competition=competition,
        status='ACTIVE'
    ).select_related('judge__user')

    if judge_assignments:
        elements.append(Paragraph(
            "We, the undersigned, hereby certify that this competition was conducted in accordance "
            "with all applicable rules and regulations, and that the results presented herein are "
            "true and accurate.",
            ParagraphStyle('CertText',
                          parent=styles['Normal'],
                          fontSize=11,
                          spaceAfter=25,
                          textColor=text_color,
                          leading=14,
                          alignment=4)
        ))

    signature_data = []
    for i in range(0, len(judge_assignments), 2):
        row = []
        for j in range(2):
            if i + j < len(judge_assignments):
                assignment = judge_assignments[i + j]
                judge_name = assignment.judge.user.get_full_name()
                cell = [
                    Spacer(1, 40),
                    HRFlowable(
                        width="90%",
                        thickness=1,
                        color=accent_color,
                        spaceBefore=0,
                        spaceAfter=5,
                        hAlign='CENTER'
                    ),
                    Paragraph(judge_name.upper(),
                            ParagraphStyle('JudgeName',
                                         parent=styles['Normal'],
                                         fontSize=12,
                                         textColor=accent_color,
                                         alignment=1,
                                         borderPadding=6,
                                         leading=14,
                                         fontName='Helvetica-Bold')),
                    Paragraph('Competition Judge',
                            ParagraphStyle('JudgeTitle',
                                         parent=styles['Normal'],
                                         fontSize=10,
                                         textColor=secondary_color,
                                         alignment=1,
                                         leading=12,
                                         fontName='Helvetica'))
                ]
                row.append(cell)
            else:
                row.append('')
        signature_data.append(row)

    signature_grid = Table(signature_data, colWidths=[250, 250])
    signature_grid.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('TOPPADDING', (0, 0), (-1, -1), 12),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 30),
        ('LEFTPADDING', (0, 0), (-1, -1), 20),
        ('RIGHTPADDING', (0, 0), (-1, -1), 20),
    ]))
    elements.append(signature_grid)

    elements.append(Spacer(1, 20))
    chair_data = [
        [Spacer(1, 50)],
        [HRFlowable(
            width="90%",
            thickness=1,
            color=accent_color,
            spaceBefore=0,
            spaceAfter=5,
            hAlign='CENTER'
        )],
        [Paragraph('Competition Chairperson',
                  ParagraphStyle('ChairTitle',
                               parent=styles['Normal'],
                               fontSize=10,
                               textColor=secondary_color,
                               alignment=1,
                               fontName='Helvetica',
                               leading=14))],
        [Paragraph(datetime.now().strftime('%B %d, %Y'),
                  ParagraphStyle('DateStyle',
                               parent=styles['Normal'],
                               fontSize=9,
                               textColor=text_color,
                               alignment=1,
                               fontName='Helvetica',
                               leading=12))]
    ]

    chair_table = Table(chair_data, colWidths=[400])
    chair_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 20),
        ('RIGHTPADDING', (0, 0), (-1, -1), 20),
    ]))
    elements.append(chair_table)

    elements.append(Spacer(1, 40))
    elements.append(HRFlowable(
        width="100%",
        thickness=1,
        color=accent_color,
        spaceBefore=10,
        spaceAfter=10,
        hAlign='CENTER'
    ))

    footer_text = (
        f"OFFICIAL DOCUMENT \u2022 Generated on {datetime.now().strftime('%B %d, %Y at %I:%M %p')} \u2022 "
        f"{competition.name}"
    )
    elements.append(Paragraph(footer_text, ParagraphStyle(
        'Footer',
        parent=styles['Normal'],
        fontSize=8,
        textColor=text_color,
        alignment=1,
        leading=10
    )))

    doc.build(elements)

    pdf = buffer.getvalue()
    buffer.close()
    response.write(pdf)

    return response


@login_required
def results_list(request):
    competitions = Competition.objects.prefetch_related(
        'rounds',
        'participants',
        'rounds__results',
        'rounds__results__participant',
        'rounds__criteria'
    ).order_by('-start_date')

    page_obj = Paginator(competitions, 9).get_page(request.GET.get('page'))

    competition_results = []
    for competition in page_obj:
        latest_round = competition.rounds.order_by('-order').first()

        if latest_round:
            calculate_rankings(latest_round)

            total_participants = CompetitionResult.objects.filter(
                round=latest_round
            ).count()

            top_results = CompetitionResult.objects.filter(
                round=latest_round,
                total_score__gt=0
            ).select_related('participant').order_by('rank', '-total_score')[:3]

            if top_results:
                top_results = sorted(top_results, key=lambda x: x.total_score, reverse=True)
        else:
            top_results = []
            total_participants = 0

        competition_data = {
            'competition': competition,
            'latest_round': latest_round,
            'results_visible': competition.show_results,
            'total_participants': total_participants,
            'total_rounds': competition.rounds.count(),
            'top_results': top_results if competition.show_results else []
        }
        competition_results.append(competition_data)

    return render(request, 'scoring/results_list.html', {
        'competition_results': competition_results,
        'page_obj': page_obj,
        'page_title': 'Competition Results'
    })
