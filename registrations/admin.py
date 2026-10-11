from django.contrib import admin

from .models import EventRegistration


@admin.register(EventRegistration)
class EventRegistrationAdmin(admin.ModelAdmin):
    list_display = ('contestant_name', 'target_name', 'registrant', 'status', 'created_at', 'reviewed_by')
    list_filter = ('status', 'competition', 'sport_event')
    search_fields = ('registrant__username', 'team__name', 'participant__name', 'competition__name')
    date_hierarchy = 'created_at'
    readonly_fields = ('created_at', 'reviewed_at')
