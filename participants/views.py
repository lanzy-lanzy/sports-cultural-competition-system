from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction, models
from django.core.paginator import Paginator

from competitions.models import Competition
from .models import Participant, ParticipantCompetition
from scoring.models import Score, CompetitionResult


@login_required
def participant_list(request):
    participants = Participant.objects.all().order_by('-registration_date')
    page_obj = Paginator(participants, 9).get_page(request.GET.get('page'))
    return render(request, 'participants/participant_list.html', {'page_obj': page_obj})


@login_required
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


@login_required
def create_participant(request):
    if request.method == 'POST':
        try:
            participant = Participant.objects.create(
                name=request.POST.get('name'),
                email=request.POST.get('email'),
                phone=request.POST.get('phone'),
                age=request.POST.get('age'),
                gender=request.POST.get('gender'),
                bio=request.POST.get('bio'),
                achievements=request.POST.get('achievements'),
                status='ACTIVE'
            )

            if 'profile_image' in request.FILES:
                participant.profile_image = request.FILES['profile_image']
                participant.save()

            messages.success(request, 'Participant created successfully!')

            next_url = request.POST.get('next')
            if next_url and 'assign_participants' in next_url:
                return redirect(next_url)
            return redirect('participant_list')

        except Exception as e:
            messages.error(request, f'Error creating participant: {str(e)}')

    next_url = request.GET.get('next', '')

    return render(request, 'participants/participant_management/create_participant.html', {
        'next_url': next_url
    })


@login_required
def delete_participant(request, participant_id):
    if not request.user.is_superuser:
        messages.error(request, "You don't have permission to delete participants.")
        return redirect('participant_list')

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


@login_required
def edit_participant(request, participant_id):
    participant = get_object_or_404(Participant, id=participant_id)

    if request.method == 'POST':
        try:
            participant.name = request.POST.get('name', participant.name)
            participant.email = request.POST.get('email', participant.email)
            participant.phone = request.POST.get('phone', participant.phone)
            participant.age = request.POST.get('age') or None
            participant.gender = request.POST.get('gender', participant.gender)
            participant.bio = request.POST.get('bio', participant.bio)
            participant.achievements = request.POST.get('achievements', participant.achievements)
            participant.status = request.POST.get('status', participant.status)

            if 'profile_image' in request.FILES:
                participant.profile_image = request.FILES['profile_image']
            elif request.POST.get('remove_image') == 'true':
                participant.profile_image = None

            participant.save()
            messages.success(request, 'Participant updated successfully!')
        except Exception as e:
            messages.error(request, f'Error updating participant: {str(e)}')

        return redirect('participant_list')

    return render(request, 'participants/participant_management/edit_participant.html', {
        'participant': participant
    })


@login_required
def participant_management(request):
    if not request.user.is_staff:
        messages.error(request, 'You do not have permission to access this page.')
        return redirect('dashboard')

    competitions = Competition.objects.all().order_by('-id')
    for competition in competitions:
        competition.participant_count = competition.participants.count()

    context = {
        'competitions': competitions,
    }
    return render(request, 'participants/participant_management/participant_management.html', context)


@login_required
def manage_participants(request, competition_id):
    if not request.user.is_staff:
        messages.error(request, 'You do not have permission to manage participants.')
        return redirect('competition_detail', competition_id=competition_id)

    competition = get_object_or_404(Competition, id=competition_id)
    participants = competition.participants.all()
    available_participants = Participant.objects.exclude(competitions=competition)

    context = {
        'competition': competition,
        'participants': participants,
        'available_participants': available_participants,
    }
    return render(request, 'participants/participant_management/manage_participants.html', context)


@login_required
def assign_participants(request, competition_id):
    if not request.user.is_staff:
        messages.error(request, 'You do not have permission to assign participants.')
        return redirect('competition_detail', competition_id=competition_id)

    competition = get_object_or_404(Competition, id=competition_id)

    if request.method == 'POST':
        try:
            with transaction.atomic():
                participant_ids = request.POST.getlist('participants')
                if not participant_ids:
                    messages.error(request, 'Please select at least one participant to assign.')
                    return redirect('assign_participants', competition_id=competition_id)

                participants = Participant.objects.filter(id__in=participant_ids)

                highest_number = ParticipantCompetition.objects.filter(
                    competition=competition
                ).aggregate(models.Max('number'))['number__max'] or 0
                next_number = highest_number + 1

                assignments = []
                for participant in participants:
                    if not ParticipantCompetition.objects.filter(
                        participant=participant,
                        competition=competition
                    ).exists():
                        assignments.append(
                            ParticipantCompetition(
                                participant=participant,
                                competition=competition,
                                number=next_number
                            )
                        )
                        next_number += 1

                if assignments:
                    ParticipantCompetition.objects.bulk_create(assignments)
                    messages.success(request, f'{len(assignments)} participant(s) assigned successfully.')
                else:
                    messages.warning(request, 'Selected participants are already assigned to this competition.')

                return redirect('manage_participants', competition_id=competition_id)

        except Exception as e:
            messages.error(request, f'Error assigning participants: {str(e)}')
            return redirect('assign_participants', competition_id=competition_id)

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


@login_required
def remove_participant_from_competition(request, competition_id, participant_id):
    try:
        competition = Competition.objects.get(id=competition_id)
        participant = Participant.objects.get(id=participant_id)

        competition.participants.remove(participant)

        messages.success(request, f'Successfully removed {participant.name} from {competition.name}')
    except Competition.DoesNotExist:
        messages.error(request, 'Competition not found.')
    except Participant.DoesNotExist:
        messages.error(request, 'Participant not found.')
    except Exception as e:
        messages.error(request, f'Error removing participant: {str(e)}')

    return redirect('manage_participants', competition_id=competition_id)
