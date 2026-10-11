from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from competitions.models import Competition
from judges.models import Judge
from participants.models import Participant

from .access import (
    MANAGEMENT_ROLES,
    administrator_required,
    get_user_role,
    management_required,
    redirect_name_for_user,
)
from .forms import ProfileForm, RegistrationForm, UserAccessForm
from .models import UserProfile


def landing_page(request):
    return render(request, 'accounts/landing_page.html')


def login_view(request):
    if request.user.is_authenticated:
        return redirect(redirect_name_for_user(request.user))

    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')
        user = authenticate(request, username=username, password=password)

        if user is not None:
            login(request, user)
            next_url = request.POST.get('next') or request.GET.get('next')
            if next_url and url_has_allowed_host_and_scheme(
                next_url,
                allowed_hosts={request.get_host()},
                require_https=request.is_secure(),
            ):
                return redirect(next_url)
            return redirect(redirect_name_for_user(user))

        messages.error(request, 'Invalid username or password. Please try again.')

    return render(request, 'accounts/login.html', {'next': request.GET.get('next', '')})


def register_view(request):
    data = None
    if request.method == 'POST':
        data = request.POST.copy()
        data.setdefault('role', UserProfile.Role.JUDGE)
        data.setdefault('password2', data.get('password1', ''))

    form = RegistrationForm(data=data)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Your account was created successfully. You can now sign in.')
        return redirect('login')

    return render(request, 'accounts/register.html', {'form': form})


@login_required
def logout_view(request):
    logout(request)
    return redirect('login')


@login_required
def portal_home(request):
    competitions = Competition.objects.filter(status__in=['ACTIVE', 'COMPLETED']).order_by('-start_date')[:8]
    return render(request, 'accounts/portal_home.html', {
        'competitions': competitions,
        'account_role': get_user_role(request.user),
    })


@login_required
def edit_profile(request):
    form = ProfileForm(request.POST or None, request.FILES or None, user=request.user)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Profile updated successfully.')
        return redirect('edit_profile')

    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    profile_image_url = None
    if profile.profile_image:
        profile_image_url = profile.profile_image.url
    elif hasattr(request.user, 'judge') and request.user.judge.profile_image:
        profile_image_url = request.user.judge.profile_image.url

    return render(request, 'accounts/profile.html', {
        'form': form,
        'profile': profile,
        'profile_image_url': profile_image_url,
    })


@login_required
def settings_view(request):
    from announcements.models import NotificationPreference

    preference, _ = NotificationPreference.objects.get_or_create(user=request.user)
    if request.method == 'POST':
        preference.email_enabled = request.POST.get('email_enabled') == 'on'
        preference.save(update_fields=['email_enabled', 'updated_at'])
        messages.success(request, 'Settings saved successfully.')
        return redirect('settings')

    return render(request, 'accounts/settings.html', {'email_enabled': preference.email_enabled})


@management_required
def dashboard(request):
    from django.db.models import Count
    from sports.models import Match, SportsEvent
    from teams.models import Team
    from scoring.models import CompetitionResult
    from scoring.services import compute_overall_medal_tally, build_overall_standings

    context = {
        'total_competitions': Competition.objects.count(),
        'active_competitions': Competition.objects.filter(status='ACTIVE').count(),
        'total_participants': Participant.objects.count(),
        'total_judges': Judge.objects.count(),
        'total_teams': Team.objects.count(),
        'total_events': SportsEvent.objects.count(),
        'total_matches': Match.objects.count(),
        'completed_matches': Match.objects.filter(status=Match.Status.COMPLETED).count(),
        'recent_competitions': Competition.objects.all().order_by('-id')[:5],
        'upcoming_events': Competition.objects.filter(status='DRAFT').order_by('start_date')[:3],
        'upcoming_matches': Match.objects.filter(
            status=Match.Status.SCHEDULED,
        ).select_related('event__competition', 'venue').order_by('scheduled_start')[:5],
    }

    for competition in context['recent_competitions']:
        competition.participant_count = competition.participants.count()
        competition.rounds_count = competition.rounds.count()

    # Current champions: the top-ranked participant in each running competition.
    champions = []
    for competition in Competition.objects.filter(status='ACTIVE'):
        standings = build_overall_standings(competition)
        participant_lookup = {p.id: p for p in competition.participants.all()}
        top = min(
            (item for item in standings.items() if item[1]['total'] > 0),
            key=lambda item: item[1]['rank'],
            default=None,
        )
        if top:
            champions.append({
                'competition': competition,
                'participant': participant_lookup.get(top[0]),
                'score': top[1]['total'],
            })
    context['current_champions'] = champions[:5]

    # Overall medal standings across all competitions.
    try:
        tally = compute_overall_medal_tally()
        context['medal_standings'] = tally['rows'][:5]
    except Exception:
        context['medal_standings'] = []

    return render(request, 'accounts/dashboard.html', context)


@administrator_required
def user_management(request):
    users = User.objects.select_related('account_profile').order_by('username')
    page_obj = Paginator(users, 20).get_page(request.GET.get('page'))
    return render(request, 'accounts/user_management.html', {
        'page_obj': page_obj,
        'users': page_obj,
        'role_choices': UserProfile.Role.choices,
        'management_roles': MANAGEMENT_ROLES,
    })


@administrator_required
@require_POST
def update_user_access(request, user_id):
    target_user = get_object_or_404(User, id=user_id)
    if target_user == request.user:
        messages.error(request, 'You cannot change your own role or deactivate your own account.')
        return redirect('user_management')
    if target_user.is_superuser and not request.user.is_superuser:
        messages.error(request, 'Only a superuser can update another superuser.')
        return redirect('user_management')

    form = UserAccessForm(request.POST)
    if form.is_valid():
        form.save(target_user)
        from audit.models import record_action_from_request
        record_action_from_request(
            request,
            'ACCESS_UPDATED',
            target=target_user,
            details=f'Access settings updated for {target_user.username}',
        )
        messages.success(request, f'Access settings updated for {target_user.username}.')
    else:
        messages.error(request, 'The selected access settings are invalid.')
    return redirect(f'{reverse("user_management")}?page={request.GET.get("page", 1)}')
