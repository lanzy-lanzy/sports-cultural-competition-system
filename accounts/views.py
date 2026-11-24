from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count, ProtectedError, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils import timezone
from django.views.decorators.http import require_POST

from competitions.models import Competition
from judges.models import Judge, JudgeAssignment
from participants.models import Participant, ParticipantCompetition
from scoring.models import Score
from scoring.services import COUNTED_STATUSES, calculate_participant_total_score

from .access import (
    MANAGEMENT_ROLES,
    administrator_required,
    get_user_role,
    management_required,
    redirect_name_for_user,
    role_required,
)
from .forms import ProfileForm, RegistrationForm, UserAccessForm
from .models import UserProfile


def _scorecard_for(competition, round_obj, is_live):
    """Bundle real round data (entries, judges, ranked scores) for the landing score sheet."""
    entries = list(competition.participants.all())
    criteria = list(round_obj.criteria.all())

    counted_scores = Score.objects.filter(criterion__round=round_obj, status__in=COUNTED_STATUSES)
    judges_total = (
        JudgeAssignment.objects
        .filter(competition=competition, status='ACTIVE', rounds=round_obj)
        .count()
    )
    judges_done = counted_scores.values('judge_id').distinct().count()
    judges_total = judges_total or judges_done

    expected = max(len(entries) * len(criteria) * judges_total, 1)
    completion = min(int(100 * counted_scores.count() / expected), 100) if counted_scores.exists() else 0

    number_map = {
        item.participant_id: item.number
        for item in ParticipantCompetition.objects.filter(competition=competition)
    }

    ranked = sorted(
        (
            (participant, calculate_participant_total_score(participant, round_obj, include_draft=False))
            for participant in entries
        ),
        key=lambda pair: pair[1],
        reverse=True,
    )

    leaderboard = []
    current_rank = 1
    previous_score = None
    for index, (participant, total) in enumerate(ranked, start=1):
        if total <= 0 or len(leaderboard) == 3:
            break
        if total != previous_score:
            current_rank = index
        previous_score = total
        number = number_map.get(participant.id)
        leaderboard.append({
            'rank': '%02d' % current_rank,
            'name': participant.name,
            'number': '%02d' % number if number else '',
            'score': total,
        })

    return {
        'competition_name': competition.name,
        'round_name': round_obj.name,
        'round_label': 'Round %d of %d' % (round_obj.order, competition.rounds.count()),
        'entries': len(entries),
        'criteria': len(criteria),
        'judges_done': judges_done,
        'judges_total': judges_total,
        'percent': completion,
        'status_label': 'LIVE' if is_live else 'FINAL',
        'has_scores': counted_scores.exists(),
        'leaderboard': leaderboard,
    }


def landing_scorecard():
    """Pick the most presentable round with real data: live scoring, then final results."""
    competitions = list(Competition.objects.exclude(kind=Competition.Kind.SPORTS).order_by('-start_date', '-id'))
    active = [c for c in competitions if c.status == 'ACTIVE']

    # 1) Live scoring: the most recent active competition with an ongoing, scored round.
    for competition in active:
        round_obj = competition.rounds.filter(status='ONGOING').order_by('order').first()
        if round_obj and Score.objects.filter(criterion__round=round_obj, status__in=COUNTED_STATUSES).exists():
            return _scorecard_for(competition, round_obj, is_live=True)

    # 2) Latest completed round with certified scores, presented as final results.
    for competition in competitions:
        round_obj = competition.rounds.filter(status='COMPLETED').order_by('-order').first()
        if round_obj and Score.objects.filter(criterion__round=round_obj, status__in=COUNTED_STATUSES).exists():
            return _scorecard_for(competition, round_obj, is_live=False)

    # 3) A just-started round (real counts, no certified scores yet).
    for competition in active:
        round_obj = competition.rounds.filter(status='ONGOING').order_by('order').first()
        if round_obj:
            return _scorecard_for(competition, round_obj, is_live=True)

    return None


def landing_page(request):
    return render(request, 'accounts/landing_page.html', {'scorecard': landing_scorecard()})


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
    if get_user_role(request.user) == UserProfile.Role.TEAM_MANAGER:
        return team_manager_dashboard(request)
    competitions = Competition.objects.filter(status__in=['ACTIVE', 'COMPLETED']).order_by('-start_date')[:8]
    role = get_user_role(request.user)
    return render(request, 'accounts/portal_home.html', {
        'competitions': competitions,
        'account_role': role,
        'participant_has_profile': role == UserProfile.Role.PARTICIPANT and Participant.objects.filter(user=request.user).exists(),
    })


@role_required(UserProfile.Role.TEAM_MANAGER)
def team_manager_dashboard(request):
    from registrations.services import registrations_for_user
    from sports.models import Match
    from teams.models import Team, TeamMembership
    teams = Team.objects.filter(staff_assignments__user=request.user).distinct().annotate(
        player_count=Count('memberships', distinct=True),
        event_count=Count('event_entries', distinct=True, filter=Q(event_entries__status='CONFIRMED')),
        pending_count=Count('registrations', distinct=True, filter=Q(registrations__status__in=['PENDING', 'UNDER_REVIEW'])),
    )
    team_ids = teams.values('pk')
    registrations = registrations_for_user(request.user)
    counts = registrations.aggregate(
        total=Count('pk'),
        pending=Count('pk', filter=Q(status__in=['PENDING', 'UNDER_REVIEW'])),
        approved=Count('pk', filter=Q(status='APPROVED')),
        rejected=Count('pk', filter=Q(status='REJECTED')),
    )
    memberships = TeamMembership.objects.filter(team_id__in=team_ids)
    upcoming = Match.objects.filter(
        entries__team_id__in=team_ids,
        status__in=[Match.Status.SCHEDULED, Match.Status.ONGOING],
    ).filter(Q(scheduled_start__gte=timezone.now()) | Q(status=Match.Status.ONGOING)).distinct().select_related(
        'event__competition', 'venue',
    ).prefetch_related('entries__team', 'entries__participant').order_by('scheduled_start', 'pk')[:6]

    comp_q = (request.GET.get('comp_q') or '').strip()
    comp_kind = (request.GET.get('comp_kind') or '').strip()
    comp_status = (request.GET.get('comp_status') or '').strip()
    comp_year = (request.GET.get('comp_year') or '').strip()

    base_comps = Competition.objects.filter(status__in=['ACTIVE', 'COMPLETED']).prefetch_related(
        'sport_events__sport_type', 'sport_events__venue',
    )
    comp_years = sorted(
        {dt.year for dt in base_comps.values_list('start_date', flat=True) if dt},
        reverse=True,
    )

    competitions_qs = base_comps
    if comp_q:
        competitions_qs = competitions_qs.filter(
            Q(name__icontains=comp_q)
            | Q(description__icontains=comp_q)
            | Q(sport_events__name__icontains=comp_q)
            | Q(sport_events__sport_type__name__icontains=comp_q)
            | Q(sport_events__venue__name__icontains=comp_q)
        ).distinct()
    if comp_kind in (Competition.Kind.SPORTS, Competition.Kind.CULTURAL):
        competitions_qs = competitions_qs.filter(kind=comp_kind)
    else:
        comp_kind = ''
    if comp_status in ('ACTIVE', 'COMPLETED'):
        competitions_qs = competitions_qs.filter(status=comp_status)
    else:
        comp_status = ''
    if comp_year.isdigit():
        competitions_qs = competitions_qs.filter(start_date__year=int(comp_year))
    else:
        comp_year = ''

    workspace_competitions = list(
        competitions_qs.annotate(event_count=Count('sport_events', distinct=True))
        .order_by('-start_date', '-id')[:12]
    )

    return render(request, 'accounts/team_manager_dashboard.html', {
        'managed_teams': teams,
        'team_count': teams.count(),
        'player_count': memberships.filter(status='ACTIVE', participant__status='ACTIVE').count(),
        'event_assignment_count': memberships.filter(events__isnull=False).count(),
        'registration_counts': counts,
        'recent_registrations': registrations.select_related('team', 'sport_event', 'competition', 'registrant')[:8],
        'upcoming_matches': upcoming,
        'workspace_competitions': workspace_competitions,
        'comp_years': comp_years,
        'comp_filters': {
            'q': comp_q,
            'kind': comp_kind,
            'status': comp_status,
            'year': comp_year,
        },
        'has_comp_filter': bool(comp_q or comp_kind or comp_status or comp_year),
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
        preference.sms_enabled = request.POST.get('sms_enabled') == 'on'
        preference.save(update_fields=['sms_enabled', 'updated_at'])
        messages.success(request, 'Settings saved successfully.')
        return redirect('settings')

    return render(request, 'accounts/settings.html', {
        'sms_enabled': preference.sms_enabled,
        'account_phone': request.user.account_profile.phone if hasattr(request.user, 'account_profile') else '',
    })


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
    from django.db.models import Q
    from sports.models import SportsEvent

    q = (request.GET.get('q') or '').strip()
    role_filter = (request.GET.get('role') or '').strip()

    all_users = User.objects.select_related('account_profile')
    stats = {
        'total': all_users.count(),
        'active': all_users.filter(is_active=True).count(),
        'tournament_managers': all_users.filter(account_profile__role=UserProfile.Role.TOURNAMENT_MANAGER).count(),
        'team_managers': all_users.filter(account_profile__role=UserProfile.Role.TEAM_MANAGER).count(),
    }

    users = all_users.prefetch_related(
        'managed_sport_events',
        'team_staff_assignments__team',
    ).order_by('username')
    if q:
        users = users.filter(
            Q(username__icontains=q)
            | Q(first_name__icontains=q)
            | Q(last_name__icontains=q)
        )
    if role_filter and role_filter in UserProfile.Role.values:
        users = users.filter(account_profile__role=role_filter)
    else:
        role_filter = ''

    page_obj = Paginator(users, 20).get_page(request.GET.get('page'))
    sport_events = list(
        SportsEvent.objects.select_related('competition', 'sport_type', 'tournament_manager')
        .order_by('competition__name', 'name')
    )

    return render(request, 'accounts/user_management.html', {
        'page_obj': page_obj,
        'users': page_obj,
        'stats': stats,
        'query': q,
        'role_filter': role_filter,
        'role_choices': UserProfile.Role.choices,
        'management_roles': MANAGEMENT_ROLES,
        'sport_events': sport_events,
    })


@administrator_required
@require_POST
def admin_create_user(request):
    from sports.models import SportsEvent
    from .access import sync_staff_status

    username = (request.POST.get('username') or '').strip()
    first_name = (request.POST.get('first_name') or '').strip()
    last_name = (request.POST.get('last_name') or '').strip()
    password = (request.POST.get('password') or '').strip()
    role = (request.POST.get('role') or UserProfile.Role.TOURNAMENT_MANAGER).strip()
    is_active = request.POST.get('is_active') == 'on'

    if not username or not password:
        messages.error(request, 'Username and password are required to create an account.')
        return redirect('user_management')
    if len(password) < 6:
        messages.error(request, 'Password must be at least 6 characters long.')
        return redirect('user_management')
    if User.objects.filter(username__iexact=username).exists():
        messages.error(request, f'Username "{username}" is already taken.')
        return redirect('user_management')
    if role not in UserProfile.Role.values:
        messages.error(request, 'Select a valid access role.')
        return redirect('user_management')

    with transaction.atomic():
        new_user = User.objects.create_user(
            username=username,
            password=password,
            first_name=first_name,
            last_name=last_name,
            is_active=is_active,
        )
        profile, _ = UserProfile.objects.get_or_create(user=new_user)
        profile.role = role
        profile.save(update_fields=['role', 'updated_at'])
        sync_staff_status(new_user, role)

        if role == UserProfile.Role.TOURNAMENT_MANAGER:
            event_ids = [int(eid) for eid in request.POST.getlist('sport_event_ids') if str(eid).isdigit()]
            if event_ids:
                SportsEvent.objects.filter(id__in=event_ids).update(tournament_manager=new_user)

    from audit.models import record_action_from_request
    record_action_from_request(
        request,
        'USER_CREATED',
        target=new_user,
        details=f'Created user account {new_user.username} with role {role}',
    )
    messages.success(request, f'Account "{new_user.username}" created successfully.')
    return redirect('user_management')


@administrator_required
@require_POST
def update_user_access(request, user_id):
    from sports.models import SportsEvent

    target_user = get_object_or_404(User, id=user_id)
    if target_user == request.user:
        messages.error(request, 'You cannot change your own role or deactivate your own account.')
        return redirect('user_management')
    if target_user.is_superuser and not request.user.is_superuser:
        messages.error(request, 'Only a superuser can update another superuser.')
        return redirect('user_management')

    form = UserAccessForm(request.POST)
    if form.is_valid():
        with transaction.atomic():
            form.save(target_user)
            new_password = (request.POST.get('new_password') or '').strip()
            if new_password:
                if len(new_password) < 6:
                    messages.warning(request, 'Password was not changed (minimum 6 characters required).')
                else:
                    target_user.set_password(new_password)
                    target_user.save(update_fields=['password'])

            if request.POST.get('sync_sport_events') == '1':
                if form.cleaned_data['role'] == UserProfile.Role.TOURNAMENT_MANAGER:
                    selected_ids = [int(eid) for eid in request.POST.getlist('sport_event_ids') if str(eid).isdigit()]
                    SportsEvent.objects.filter(tournament_manager=target_user).exclude(id__in=selected_ids).update(tournament_manager=None)
                    if selected_ids:
                        SportsEvent.objects.filter(id__in=selected_ids).update(tournament_manager=target_user)
                else:
                    SportsEvent.objects.filter(tournament_manager=target_user).update(tournament_manager=None)

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


@administrator_required
@require_POST
def delete_user(request, user_id):
    target_user = get_object_or_404(User, id=user_id)
    page = request.POST.get('page') or request.GET.get('page') or 1
    list_url = f'{reverse("user_management")}?page={page}'

    if target_user == request.user:
        messages.error(request, 'You cannot delete your own account.')
        return redirect(list_url)
    if target_user.is_superuser and not request.user.is_superuser:
        messages.error(request, 'Only a superuser can delete another superuser.')
        return redirect(list_url)

    username = target_user.username
    try:
        with transaction.atomic():
            target_user.delete()
    except ProtectedError:
        messages.error(
            request,
            f'Cannot delete "{username}" because this account owns competitions, teams, or announcements. Deactivate the account instead.',
        )
        return redirect(list_url)

    from audit.models import record_action_from_request
    record_action_from_request(
        request,
        'USER_DELETED',
        details=f'Deleted user account: {username}',
    )
    messages.success(request, f'Successfully deleted user account: {username}.')
    return redirect(list_url)


@administrator_required
@require_POST
def bulk_delete_users(request):
    raw_ids = request.POST.getlist('user_ids')
    user_ids = [int(uid) for uid in raw_ids if str(uid).isdigit()]
    page = request.POST.get('page') or request.GET.get('page') or 1
    list_url = f'{reverse("user_management")}?page={page}'

    if not user_ids:
        messages.warning(request, 'Select at least one user account to delete.')
        return redirect(list_url)

    targets = list(User.objects.filter(id__in=user_ids).order_by('username'))
    if not targets:
        messages.warning(request, 'No matching user accounts were found to delete.')
        return redirect(list_url)

    deleted_usernames = []
    skipped_self = False
    skipped_superusers = []
    blocked_protected = []

    for target_user in targets:
        if target_user == request.user:
            skipped_self = True
            continue
        if target_user.is_superuser and not request.user.is_superuser:
            skipped_superusers.append(target_user.username)
            continue
        username = target_user.username
        try:
            with transaction.atomic():
                target_user.delete()
            deleted_usernames.append(username)
        except ProtectedError:
            blocked_protected.append(username)

    if deleted_usernames:
        from audit.models import record_action_from_request
        preview = ', '.join(deleted_usernames[:10]) + (' ...' if len(deleted_usernames) > 10 else '')
        record_action_from_request(
            request,
            'USER_BULK_DELETED',
            details=f'Bulk deleted {len(deleted_usernames)} user account(s): {preview}',
        )
        messages.success(request, f'Successfully deleted {len(deleted_usernames)} user account(s).')

    if skipped_self:
        messages.warning(request, 'Your own account was skipped and cannot be deleted.')
    if skipped_superusers:
        messages.warning(
            request,
            f'Skipped superuser account(s): {", ".join(skipped_superusers)}.',
        )
    if blocked_protected:
        messages.error(
            request,
            f'Could not delete {", ".join(blocked_protected)} because they own competitions, teams, or announcements. Deactivate them instead.',
        )

    return redirect(list_url)
