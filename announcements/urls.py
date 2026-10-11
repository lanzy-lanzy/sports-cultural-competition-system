from django.urls import path

from . import views


urlpatterns = [
    path('announcements/', views.announcement_list, name='announcement_list'),
    path('announcements/create/', views.create_announcement, name='create_announcement'),
    path('announcements/<int:announcement_id>/edit/', views.edit_announcement, name='edit_announcement'),
    path('announcements/<int:announcement_id>/toggle/', views.toggle_announcement_publish, name='toggle_announcement_publish'),
    path('announcements/<int:announcement_id>/delete/', views.delete_announcement, name='delete_announcement'),
    path('announcements/public/', views.announcement_public, name='announcement_public'),
    path('notifications/', views.notification_list, name='notification_list'),
    path('notifications/<int:notification_id>/read/', views.mark_notification_read, name='mark_notification_read'),
    path('notifications/read-all/', views.mark_all_notifications_read, name='mark_all_notifications_read'),
]
