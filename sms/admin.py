from django.contrib import admin

from .models import SmsMessage


@admin.register(SmsMessage)
class SmsMessageAdmin(admin.ModelAdmin):
    list_display = (
        'recipient', 'recipient_name', 'category', 'status', 'provider_status',
        'sender_name', 'match', 'created_at',
    )
    list_filter = ('status', 'category', 'provider_status', 'created_at')
    search_fields = ('recipient', 'recipient_name', 'body', 'error', 'semaphore_message_id')
    date_hierarchy = 'created_at'
    list_select_related = ('match', 'created_by')
    readonly_fields = (
        'recipient', 'recipient_name', 'body', 'sender_name', 'category', 'status',
        'semaphore_message_id', 'provider_status', 'error', 'match', 'created_by',
        'created_at',
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
