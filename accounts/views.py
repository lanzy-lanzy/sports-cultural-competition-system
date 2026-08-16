from django.shortcuts import render, redirect
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import transaction

from competitions.models import Competition
from participants.models import Participant
from judges.models import Judge


def landing_page(request):
    return render(request, 'accounts/landing_page.html')


def login_view(request):
    if request.method == 'POST':
        username = request.POST['username']
        password = request.POST['password']
        user = authenticate(request, username=username, password=password)

        if user is not None:
            login(request, user)

            if hasattr(user, 'judge'):
                return redirect('judge_dashboard')
            elif user.is_superuser:
                return redirect('dashboard')

        else:
            messages.error(request, 'Invalid username or password. Please try again.')

    return render(request, 'accounts/login.html')


def register_view(request):
    if request.method == 'POST':
        with transaction.atomic():
            user = User.objects.create_user(
                username=request.POST['username'],
                email=request.POST['email'],
                password=request.POST['password1']
            )

            user.first_name = request.POST['full_name'].split()[0]
            user.last_name = ' '.join(request.POST['full_name'].split()[1:])
            user.save()

            Judge.objects.create(
                user=user,
                phone=request.POST['phone'],
                status='ACTIVE'
            )

            return redirect('login')

    return render(request, 'accounts/register.html')


@login_required
def logout_view(request):
    logout(request)
    return redirect('login')


@login_required
def edit_profile(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        email = request.POST.get('email')
        profile_image = request.FILES.get('profile_image')

        user = request.user
        user.username = username
        user.email = email

        if profile_image and hasattr(user, 'judge'):
            user.judge.profile_image = profile_image
            user.judge.save()

        user.save()
        messages.success(request, 'Profile updated successfully.')
        if hasattr(user, 'judge'):
            return redirect('judge_dashboard')
        return redirect('dashboard')

    return render(request, 'accounts/profile.html')


@login_required
def settings_view(request):
    return render(request, 'accounts/settings.html')


@login_required
def dashboard(request):
    context = {
        'total_competitions': Competition.objects.count(),
        'active_competitions': Competition.objects.filter(status='ACTIVE').count(),
        'total_participants': Participant.objects.count(),
        'total_judges': Judge.objects.count(),
        'recent_competitions': Competition.objects.all().order_by('-id')[:5],
        'upcoming_events': Competition.objects.filter(status='DRAFT').order_by('start_date')[:3],
    }

    for competition in context['recent_competitions']:
        competition.participant_count = competition.participants.count()
        competition.rounds_count = competition.rounds.count()

    for judge in Judge.objects.all():
        judge.scores_count = judge.scores.count()

    return render(request, 'accounts/dashboard.html', context)
