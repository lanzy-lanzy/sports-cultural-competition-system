from django.urls import path

from . import views


urlpatterns = [
    path('sms/', views.sms_dashboard, name='sms_dashboard'),
    path('sms/bulk/', views.sms_bulk_notify, name='sms_bulk_notify'),
    path('sms/matches/<int:match_id>/notify/', views.sms_notify_match, name='sms_notify_match'),
    path('sms/rounds/<int:round_id>/notify/', views.sms_notify_round, name='sms_notify_round'),
]
