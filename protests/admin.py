from django.contrib import admin

from .models import Protest


@admin.register(Protest)
class ProtestAdmin(admin.ModelAdmin):
    list_display = ('title', 'submitter', 'target_name', 'status', 'submitted_at', 'reviewed_by')
    list_filter = ('status', 'submitted_at')
    search_fields = ('title', 'description', 'submitter__username', 'decision')
    date_hierarchy = 'submitted_at'
    readonly_fields = ('submitted_at', 'reviewed_at')
    filter_horizontal = ('reviewers',)