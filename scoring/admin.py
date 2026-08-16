from django.contrib import admin
from .models import Score, CompetitionResult


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
