from functools import wraps

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied

from .models import UserProfile


MANAGEMENT_ROLES = {
    UserProfile.Role.ADMINISTRATOR,
    UserProfile.Role.EVENT_ORGANIZER,
    UserProfile.Role.SPORTS_COORDINATOR,
    UserProfile.Role.CULTURAL_COORDINATOR,
}

PUBLIC_REGISTRATION_ROLES = {
    UserProfile.Role.TEAM_MANAGER,
    UserProfile.Role.PARTICIPANT,
    UserProfile.Role.JUDGE,
    UserProfile.Role.SPECTATOR,
}


def get_user_role(user):
    if not user or not user.is_authenticated:
        return None
    if user.is_superuser:
        return UserProfile.Role.ADMINISTRATOR
    try:
        return user.account_profile.role
    except UserProfile.DoesNotExist:
        if hasattr(user, 'judge'):
            return UserProfile.Role.JUDGE
        if user.is_staff:
            return UserProfile.Role.EVENT_ORGANIZER
        return UserProfile.Role.SPECTATOR


def user_has_role(user, *roles):
    return get_user_role(user) in set(roles)


def role_required(*roles):
    def decorator(view_func):
        @login_required
        @wraps(view_func)
        def wrapped(request, *args, **kwargs):
            if not user_has_role(request.user, *roles):
                raise PermissionDenied('Your account role cannot access this page.')
            return view_func(request, *args, **kwargs)

        return wrapped

    return decorator


management_required = role_required(*MANAGEMENT_ROLES)
administrator_required = role_required(UserProfile.Role.ADMINISTRATOR)
judge_required = role_required(UserProfile.Role.JUDGE)


def sync_staff_status(user, role):
    if user.is_superuser:
        return
    should_be_staff = role in MANAGEMENT_ROLES
    if user.is_staff != should_be_staff:
        user.is_staff = should_be_staff
        user.save(update_fields=['is_staff'])


def redirect_name_for_user(user):
    role = get_user_role(user)
    if role in MANAGEMENT_ROLES:
        return 'dashboard'
    if role == UserProfile.Role.JUDGE:
        return 'judge_dashboard'
    return 'portal_home'

