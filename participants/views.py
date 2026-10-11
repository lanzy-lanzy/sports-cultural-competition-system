from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction, models
from django.core.paginator import Paginator
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from competitions.models import Competition
from .models import Participant, ParticipantCompetition
from .forms import ParticipantForm
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
        'form_description': 'Create an athlete profile, classification, and identification record.',
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
        'form_description': f'Update {participant.participant_id} and their athlete information.',
        'submit_label': 'Save participant',
    })


@role_required(UserProfile.Role.PARTICIPANT)
def my_participant_profile(request):
    participant = Participant.objects.filter(user=request.user).first()
    if participant is None and request.user.email:
        participant = Participant.objects.filter(
            user__isnull=True,
            email__iexact=request.user.email,
        ).first()

    initial = None
    if participant is None:
        initial = {
            'name': request.user.get_full_name(),
            'email': request.user.email,
            'phone': request.user.account_profile.phone,
        }

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
        participant.save()
        messages.success(request, 'Your participant profile was saved successfully.')
        return redirect('my_participant_profile')

    history = ParticipantCompetition.objects.none()
    if participant:
        history = ParticipantCompetition.objects.filter(
            participant=participant,
        ).select_related('competition').order_by('-competition__start_date')

    return render(request, 'participants/my_participant_profile.html', {
        'form': form,
        'participant': participant,
        'participant_competitions': history,
    })


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


@management_required
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
