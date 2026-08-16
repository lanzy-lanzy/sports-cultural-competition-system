from django.urls import path
from . import views

urlpatterns = [
    path('judge-management/', views.judge_management, name='judge_management'),
    path('competitions/<int:competition_id>/judges/', views.manage_judges, name='manage_judges'),
    path('competitions/<int:competition_id>/judges/assign/', views.assign_judges, name='assign_judges'),
    path('competitions/<int:competition_id>/judges/<int:assignment_id>/edit/',
         views.edit_judge_assignment, name='edit_judge_assignment'),
    path('competitions/<int:competition_id>/judges/<int:assignment_id>/delete/',
         views.delete_judge_assignment, name='delete_judge_assignment'),
    path('judge/dashboard/', views.judge_dashboard, name='judge_dashboard'),
    path('judge/profile/', views.judge_profile, name='judge_profile'),
    path('judge/history/', views.judge_history, name='judge_history'),
]
