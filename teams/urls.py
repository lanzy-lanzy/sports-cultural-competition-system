from django.urls import path

from . import views


urlpatterns = [
    path('teams/', views.team_list, name='team_list'),
    path('teams/create/', views.create_team, name='create_team'),
    path('teams/<int:team_id>/', views.team_detail, name='team_detail'),
    path('teams/<int:team_id>/edit/', views.edit_team, name='edit_team'),
    path('teams/<int:team_id>/members/add/', views.add_team_member, name='add_team_member'),
    path('teams/<int:team_id>/members/<int:membership_id>/remove/', views.remove_team_member, name='remove_team_member'),
    path('teams/<int:team_id>/staff/add/', views.add_team_staff, name='add_team_staff'),
    path('teams/<int:team_id>/staff/<int:assignment_id>/remove/', views.remove_team_staff, name='remove_team_staff'),
    path('teams/<int:team_id>/status/', views.update_team_status, name='update_team_status'),
]
