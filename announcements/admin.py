from django.contrib import admin

from .models import Announcement, Notification, NotificationPreference


@admin.register(Announcement)
class AnnouncementAdmin(admin.ModelAdmin):
    list_display = ('title', 'audience', 'competition', 'is_published', 'published_at', 'created_by', 'created_at')
    list_filter = ('is_published', 'audience')
    search_fields = ('title', 'body')
    date_hierarchy = 'created_at'


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ('recipient', 'title', 'is_read', 'created_at')
    list_filter = ('is_read', 'created_at')
    search_fields = ('recipient__username', 'title')


@admin.register(NotificationPreference)
class NotificationPreferenceAdmin(admin.ModelAdmin):
    list_display = ('user', 'email_enabled')
    list_filter = ('email_enabled',)
    search_fields = ('user__username', 'user__email')
