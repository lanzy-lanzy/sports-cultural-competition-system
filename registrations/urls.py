from django.urls import path

from . import views


urlpatterns = [
    path('registrations/register/', views.register_for_event, name='register_for_event'),
    path('registrations/my/', views.my_registrations, name='my_registrations'),
    path('registrations/review/', views.registration_review_queue, name='registration_review_queue'),
    path('registrations/<int:registration_id>/review/', views.registration_review, name='registration_review'),
    path('registrations/templates/', views.registration_templates, name='registration_templates'),
]
