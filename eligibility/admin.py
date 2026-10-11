from django.contrib import admin

from .models import EligibilityRecord


@admin.register(EligibilityRecord)
class EligibilityRecordAdmin(admin.ModelAdmin):
    list_display = ('participant', 'competition', 'status', 'submitted_at', 'reviewed_by', 'reviewed_at')
    list_filter = ('status', 'competition')
    search_fields = ('participant__name', 'competition__name', 'notes')
    date_hierarchy = 'submitted_at'
    readonly_fields = ('submitted_at', 'reviewed_at')
