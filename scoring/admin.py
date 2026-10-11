from django.contrib import admin
from .models import Score, CompetitionResult, Award, AwardRecipient


@admin.register(Score)
class ScoreAdmin(admin.ModelAdmin):
    list_display = ('participant', 'criterion', 'judge', 'score', 'status', 'timestamp')
    list_filter = ('status', 'criterion', 'judge')
    search_fields = ('participant__name', 'criterion__name', 'judge__user__username')
    date_hierarchy = 'timestamp'


@admin.register(CompetitionResult)
class CompetitionResultAdmin(admin.ModelAdmin):
    list_display = ('competition', 'participant', 'round', 'total_score', 'rank', 'timestamp')
    list_filter = ('competition', 'round')
    search_fields = ('participant__name',)
    date_hierarchy = 'timestamp'


class AwardRecipientInline(admin.TabularInline):
    model = AwardRecipient
    extra = 0
    autocomplete_fields = ('participant', 'team')


@admin.register(Award)
class AwardAdmin(admin.ModelAdmin):
    list_display = ('name', 'competition', 'type', 'rank', 'is_active')
    list_filter = ('type', 'is_active', 'competition')
    search_fields = ('name', 'competition__name')
    inlines = [AwardRecipientInline]


@admin.register(AwardRecipient)
class AwardRecipientAdmin(admin.ModelAdmin):
    list_display = ('award', 'display_name', 'recipient_type', 'awarded_at')
    list_filter = ('recipient_type', 'award')
    search_fields = ('participant__name', 'team__name', 'award__name')
