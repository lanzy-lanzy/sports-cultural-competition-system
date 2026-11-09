from django.urls import path

from . import views


urlpatterns = [
    path('sms/', views.sms_dashboard, name='sms_dashboard'),
    path('sms/matches/<int:match_id>/notify/', views.sms_notify_match, name='sms_notify_match'),
]
