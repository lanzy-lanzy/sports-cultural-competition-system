from django.contrib import admin

from .models import AuditLog


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ('created_at', 'user', 'action', 'target_model_name', 'target_label', 'ip_address')
    list_filter = ('action', 'created_at')
    search_fields = ('user__username', 'user__email', 'details')
    date_hierarchy = 'created_at'
    readonly_fields = ('created_at', 'user', 'action', 'content_type', 'object_id', 'details', 'ip_address')

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False