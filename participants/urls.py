from django.urls import path
from . import views

urlpatterns = [
    path('participants/', views.participant_list, name='participant_list'),
    path('participants/<int:participant_id>/', views.participant_detail, name='participant_detail'),
    path('participants/<int:participant_id>/delete/', views.delete_participant, name='delete_participant'),
    path('participants/<int:participant_id>/edit/', views.edit_participant, name='edit_participant'),
    path('participants/create/', views.create_participant, name='create_participant'),
    path('participant/my-profile/', views.my_participant_profile, name='my_participant_profile'),
    path('participant-management/', views.participant_management, name='participant_management'),
    path('competitions/<int:competition_id>/participants/', views.manage_participants, name='manage_participants'),
    path('competitions/<int:competition_id>/participants/assign/', views.assign_participants, name='assign_participants'),
    path('competitions/<int:competition_id>/participants/<int:participant_id>/remove/',
         views.remove_participant_from_competition, name='remove_participant_from_competition'),
    # HTMX roster panel (inline assignment)
    path('competitions/<int:competition_id>/participants/panel/', views.roster_panel, name='roster_panel'),
    path('competitions/<int:competition_id>/participants/panel/assigned/', views.roster_assigned, name='roster_assigned'),
    path('competitions/<int:competition_id>/participants/panel/available/', views.roster_available, name='roster_available'),
    path('competitions/<int:competition_id>/participants/panel/assign/', views.roster_assign, name='roster_assign'),
    path('competitions/<int:competition_id>/participants/panel/<int:participant_id>/unassign/',
         views.roster_unassign, name='roster_unassign'),
]
