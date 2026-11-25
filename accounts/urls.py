from django.contrib.auth import views as auth_views
from django.urls import path, reverse_lazy

from . import views


urlpatterns = [
    path('', views.landing_page, name='landing_page'),
    path('guest/', views.guest_viewer, name='guest_viewer'),
    path('guest/bracket/<int:event_id>/', views.guest_bracket, name='guest_bracket'),
    path('login/', views.login_view, name='login'),
    path('register/', views.register_view, name='register'),
    path('logout/', views.logout_view, name='logout'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('portal/', views.portal_home, name='portal_home'),
    path('team-manager/', views.team_manager_dashboard, name='team_manager_dashboard'),
    path('profile/edit/', views.edit_profile, name='edit_profile'),
    path('settings/', views.settings_view, name='settings'),
    path('users/', views.user_management, name='user_management'),
    path('users/create/', views.admin_create_user, name='admin_create_user'),
    path('users/<int:user_id>/access/', views.update_user_access, name='update_user_access'),
    path('users/<int:user_id>/delete/', views.delete_user, name='delete_user'),
    path('users/bulk-delete/', views.bulk_delete_users, name='bulk_delete_users'),
    path(
        'password-reset/',
        auth_views.PasswordResetView.as_view(
            template_name='accounts/password_reset_form.html',
            email_template_name='accounts/password_reset_email.txt',
            subject_template_name='accounts/password_reset_subject.txt',
            success_url=reverse_lazy('password_reset_done'),
        ),
        name='password_reset',
    ),
    path(
        'password-reset/done/',
        auth_views.PasswordResetDoneView.as_view(template_name='accounts/password_reset_done.html'),
        name='password_reset_done',
    ),
    path(
        'password-reset/<uidb64>/<token>/',
        auth_views.PasswordResetConfirmView.as_view(
            template_name='accounts/password_reset_confirm.html',
            success_url=reverse_lazy('password_reset_complete'),
        ),
        name='password_reset_confirm',
    ),
    path(
        'password-reset/complete/',
        auth_views.PasswordResetCompleteView.as_view(
            template_name='accounts/password_reset_complete.html',
        ),
        name='password_reset_complete',
    ),
]
