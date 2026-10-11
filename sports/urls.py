from django.urls import path

from . import views


urlpatterns = [
    path('sports/hub/', views.sports_hub, name='sports_hub'),
    path('sports/matches/board/', views.match_board, name='match_board'),
    path('sports/', views.sport_type_list, name='sport_type_list'),
    path('sports/create/', views.sport_type_create, name='sport_type_create'),
    path('sports/<int:sport_type_id>/edit/', views.sport_type_edit, name='sport_type_edit'),
    path('sports/venues/', views.venue_list, name='venue_list'),
    path('sports/venues/create/', views.venue_create, name='venue_create'),
    path('sports/venues/<int:venue_id>/edit/', views.venue_edit, name='venue_edit'),
    path('sports/venues/<int:venue_id>/', views.venue_detail, name='venue_detail'),
    path('competitions/<int:competition_id>/sports/', views.competition_sport_events, name='competition_sport_events'),
    path('competitions/<int:competition_id>/sports/create/', views.create_sport_event, name='create_sport_event'),
    path('sports/events/<int:event_id>/', views.sport_event_detail, name='sport_event_detail'),
    path('sports/events/<int:event_id>/edit/', views.edit_sport_event, name='edit_sport_event'),
    path('sports/events/<int:event_id>/entries/add/', views.add_event_entry, name='add_event_entry'),
    path('sports/events/<int:event_id>/entries/<int:entry_id>/status/', views.update_entry_status, name='update_entry_status'),
    path('sports/events/<int:event_id>/entries/<int:entry_id>/remove/', views.remove_event_entry, name='remove_event_entry'),
    path('sports/events/<int:event_id>/bracket/generate/', views.generate_event_bracket, name='generate_event_bracket'),
    path('sports/events/<int:event_id>/bracket/clear/', views.clear_event_bracket, name='clear_event_bracket'),
    path('sports/events/<int:event_id>/matches/', views.match_schedule, name='match_schedule'),
    path('sports/events/<int:event_id>/standings/', views.event_standings, name='event_standings'),
    path('sports/events/<int:event_id>/bracket/', views.event_bracket, name='event_bracket'),
    path('sports/matches/<int:match_id>/edit/', views.edit_match, name='edit_match'),
    path('sports/matches/<int:match_id>/result/', views.record_match_result_view, name='record_match_result'),
]