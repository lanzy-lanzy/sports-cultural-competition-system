from django.urls import path

from . import views


urlpatterns = [
    path('reports/', views.reports_home, name='reports_home'),
    path('reports/participants.csv', views.export_participants_csv, name='export_participants_csv'),
    path('reports/rosters.csv', views.export_team_rosters_csv, name='export_team_rosters_csv'),
    path('reports/registrations.csv', views.export_registrations_csv, name='export_registrations_csv'),
    path('reports/schedule.csv', views.export_schedule_csv, name='export_schedule_csv'),
    path('reports/medal-tally.csv', views.export_medal_tally_csv, name='export_medal_tally_csv'),
    path('reports/competitions/<int:competition_id>/judge-scores.csv', views.export_judge_scores_csv, name='export_judge_scores_csv'),
    path('reports/competitions/<int:competition_id>/standings.csv', views.export_standings_csv, name='export_standings_csv'),
]