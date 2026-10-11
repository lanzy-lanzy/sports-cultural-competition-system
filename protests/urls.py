from django.urls import path

from . import views


urlpatterns = [
    path('protests/submit/', views.submit_protest, name='submit_protest'),
    path('protests/my/', views.my_protests, name='my_protests'),
    path('protests/review/', views.protest_list, name='protest_list'),
    path('protests/<int:protest_id>/', views.protest_detail, name='protest_detail'),
    path('protests/<int:protest_id>/review/', views.protest_review, name='protest_review'),
]