from django.urls import path

from . import views


urlpatterns = [
    path('eligibility/my/', views.my_eligibility, name='my_eligibility'),
    path('eligibility/', views.eligibility_list, name='eligibility_list'),
    path('eligibility/<int:record_id>/review/', views.eligibility_review, name='eligibility_review'),
]
