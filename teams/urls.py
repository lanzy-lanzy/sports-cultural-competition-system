from django.urls import path

from . import views


urlpatterns = [
    path('teams/', views.team_list, name='team_list'),
    path('teams/departments/', views.department_manage, name='department_manage'),
    path('teams/departments/<int:department_id>/toggle/', views.toggle_department, name='toggle_department'),
    path('teams/departments/<int:department_id>/delete/', views.delete_department, name='delete_department'),
    path('teams/create/', views.create_team, name='create_team'),
    path('teams/bulk-delete/', views.bulk_delete_teams, name='bulk_delete_teams'),
    path('teams/<int:team_id>/', views.team_detail, name='team_detail'),
    path('teams/<int:team_id>/edit/', views.edit_team, name='edit_team'),
    path('teams/<int:team_id>/color/', views.update_team_color, name='update_team_color'),
    path('teams/<int:team_id>/players/register/', views.register_team_player, name='register_team_player'),
    path('teams/<int:team_id>/roster/submit/', views.submit_team_roster, name='submit_team_roster'),
    path('teams/<int:team_id>/members/add/', views.add_team_member, name='add_team_member'),
    path('teams/<int:team_id>/members/bulk-delete/', views.bulk_delete_members, name='bulk_delete_members'),
    path('teams/<int:team_id>/members/<int:membership_id>/events/', views.update_member_events, name='update_member_events'),
    path('teams/<int:team_id>/members/<int:membership_id>/remove/', views.remove_team_member, name='remove_team_member'),
    path('teams/<int:team_id>/staff/add/', views.add_team_staff, name='add_team_staff'),
    path('teams/<int:team_id>/staff/<int:assignment_id>/remove/', views.remove_team_staff, name='remove_team_staff'),
    path('teams/<int:team_id>/status/', views.update_team_status, name='update_team_status'),
]
