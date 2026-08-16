from django.urls import path
from . import views

urlpatterns = [
    path('competitions/', views.competition_list, name='competition_list'),
    path('competitions/create/', views.create_competition, name='create_competition'),
    path('competitions/<int:competition_id>/', views.competition_detail, name='competition_detail'),
    path('competitions/<int:competition_id>/edit/', views.edit_competition, name='edit_competition'),
    path('competitions/<int:competition_id>/delete/', views.delete_competition, name='delete_competition'),
    path('competition/<int:competition_id>/toggle-status/', views.toggle_competition_status, name='toggle_competition_status'),

    path('competitions/<int:competition_id>/rounds/', views.manage_rounds, name='manage_rounds'),
    path('competitions/<int:competition_id>/rounds/create/', views.create_round, name='create_round'),
    path('competitions/<int:competition_id>/rounds/<int:round_id>/edit/', views.edit_round, name='edit_round'),
    path('competitions/<int:competition_id>/rounds/<int:round_id>/delete/', views.delete_round, name='delete_round'),
    path('competitions/<int:competition_id>/rounds/<int:round_id>/toggle-status/', views.toggle_round_status, name='toggle_round_status'),
    path('competitions/<int:competition_id>/rounds/<int:round_id>/start/', views.start_round, name='start_round'),
    path('competitions/<int:competition_id>/rounds/<int:round_id>/complete/', views.complete_round, name='complete_round'),
]
