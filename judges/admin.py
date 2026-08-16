from django.contrib import admin
from .models import Judge, JudgeAssignment


@admin.register(Judge)
class JudgeAdmin(admin.ModelAdmin):
    list_display = ('user', 'status', 'created_at')
    list_filter = ('status',)
    search_fields = ('user__username', 'user__first_name', 'user__last_name',)
    date_hierarchy = 'created_at'


@admin.register(JudgeAssignment)
class JudgeAssignmentAdmin(admin.ModelAdmin):
    list_display = ('judge', 'competition', 'status', 'assigned_at')
    list_filter = ('status', 'competition', 'judge')
    search_fields = ('judge__user__username', 'competition__name')
    filter_horizontal = ('rounds',)
