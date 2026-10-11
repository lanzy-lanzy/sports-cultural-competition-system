from django.urls import path

from . import views


urlpatterns = [
    path('audit/', views.audit_log_list, name='audit_log_list'),
    path('audit/clear/', views.clear_audit_logs, name='clear_audit_logs'),
]