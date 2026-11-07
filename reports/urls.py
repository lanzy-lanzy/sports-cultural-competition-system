from django.urls import path

from . import views


urlpatterns = [
    path('reports/', views.reports_home, name='reports_home'),

    # CSV exports
    path('reports/participants.csv', views.export_participants_csv, name='export_participants_csv'),
    path('reports/rosters.csv', views.export_team_rosters_csv, name='export_team_rosters_csv'),
    path('reports/registrations.csv', views.export_registrations_csv, name='export_registrations_csv'),
    path('reports/schedule.csv', views.export_schedule_csv, name='export_schedule_csv'),
    path('reports/medal-tally.csv', views.export_medal_tally_csv, name='export_medal_tally_csv'),
    path('reports/competitions/<int:competition_id>/judge-scores.csv', views.export_judge_scores_csv, name='export_judge_scores_csv'),
    path('reports/competitions/<int:competition_id>/standings.csv', views.export_standings_csv, name='export_standings_csv'),

    # PDF exports
    path('reports/participants.pdf', views.export_participants_pdf, name='export_participants_pdf'),
    path('reports/rosters.pdf', views.export_team_rosters_pdf, name='export_team_rosters_pdf'),
    path('reports/registrations.pdf', views.export_registrations_pdf, name='export_registrations_pdf'),
    path('reports/schedule.pdf', views.export_schedule_pdf, name='export_schedule_pdf'),
    path('reports/medal-tally.pdf', views.export_medal_tally_pdf, name='export_medal_tally_pdf'),
    path('reports/competitions/<int:competition_id>/judge-scores.pdf', views.export_judge_scores_pdf, name='export_judge_scores_pdf'),
    path('reports/competitions/<int:competition_id>/standings.pdf', views.export_standings_pdf, name='export_standings_pdf'),

    # Print previews
    path('reports/participants/print', views.print_participants, name='print_participants'),
    path('reports/rosters/print', views.print_team_rosters, name='print_team_rosters'),
    path('reports/registrations/print', views.print_registrations, name='print_registrations'),
    path('reports/schedule/print', views.print_schedule, name='print_schedule'),
    path('reports/medal-tally/print', views.print_medal_tally, name='print_medal_tally'),
    path('reports/competitions/<int:competition_id>/judge-scores/print', views.print_judge_scores, name='print_judge_scores'),
    path('reports/competitions/<int:competition_id>/standings/print', views.print_standings, name='print_standings'),
]
