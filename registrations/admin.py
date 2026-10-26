from django.contrib import admin
from django.contrib import messages

from .models import EventRegistration, RegistrationTemplate
from .services import force_delete_registration_template, soft_delete_registration_template


@admin.register(EventRegistration)
class EventRegistrationAdmin(admin.ModelAdmin):
    list_display = ('contestant_name', 'target_name', 'registrant', 'status', 'created_at', 'reviewed_by')
    list_filter = ('status', 'competition', 'sport_event')
    search_fields = ('registrant__username', 'team__name', 'participant__name', 'competition__name')
    date_hierarchy = 'created_at'
    readonly_fields = ('created_at', 'reviewed_at')


@admin.register(RegistrationTemplate)
class RegistrationTemplateAdmin(admin.ModelAdmin):
    list_display = ('name', 'contestant_name', 'target_name', 'status', 'created_at', 'updated_at')
    list_filter = ('status', 'competition', 'sport_event')
    search_fields = ('name', 'description', 'participant__name', 'team__name', 'competition__name')
    ordering = ('-created_at',)
    actions = ('delete_selected_templates', 'force_delete_selected_templates')

    def contestant_name(self, obj):
        return obj.contestant_name
    contestant_name.short_description = 'Contestant'

    def target_name(self, obj):
        return obj.target_name
    target_name.short_description = 'Target'

    @admin.action(description='Delete selected templates (soft delete)')
    def delete_selected_templates(self, request, queryset):
        """Soft-delete selected templates by archiving them."""
        count = queryset.filter(status__in=[RegistrationTemplate.Status.DRAFT, RegistrationTemplate.Status.ACTIVE]).count()
        queryset.update(status=RegistrationTemplate.Status.ARCHIVED)
        self.message_user(request, f'{count} template(s) soft-deleted (archived).')

    @admin.action(description='Force delete selected templates')
    def force_delete_selected_templates(self, request, queryset):
        """Force-delete selected templates permanently (bypasses all protections)."""
        count = queryset.count()
        deleted_names = list(queryset.values_list('name', flat=True))
        for template in queryset:
            template.delete()
        self.message_user(
            request,
            f'Force-deleted {count} template(s): {", ".join(deleted_names)}.'
        )
