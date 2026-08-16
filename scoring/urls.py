from django.urls import path
from . import views

urlpatterns = [
    path('results/', views.results_list, name='results_list'),
    path('competitions/<int:competition_id>/results/',
         views.competition_results_detail, name='competition_results_detail'),
    path('competitions/<int:competition_id>/results/print/',
         views.results_print, name='results_print'),
    path('competitions/<int:competition_id>/results/reveal/',
         views.results_reveal, name='results_reveal'),
    path('competitions/<int:competition_id>/results/toggle/',
         views.toggle_results_visibility, name='toggle_results_visibility'),
    path('competitions/<int:competition_id>/rounds/<int:round_id>/results/',
         views.round_results, name='round_results'),
    path('competition/<int:competition_id>/pdf-results/',
         views.generate_results_pdf, name='generate_pdf_results'),
    path('judge/scoring-panel/<int:round_id>/', views.scoring_panel, name='scoring_panel'),
    path('round/<int:round_id>/update-score/', views.update_score, name='update_score'),
]
