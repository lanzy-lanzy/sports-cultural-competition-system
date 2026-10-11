from django.contrib import admin
from .models import Participant, ParticipantCompetition


@admin.register(Participant)
class ParticipantAdmin(admin.ModelAdmin):
    list_display = ('participant_id', 'name', 'category', 'team_name', 'status', 'registration_date')
    list_filter = ('status', 'category', 'gender')
    search_fields = ('participant_id', 'name', 'email', 'phone', 'team_name')
    date_hierarchy = 'registration_date'


@admin.register(ParticipantCompetition)
class ParticipantCompetitionAdmin(admin.ModelAdmin):
    list_display = ('participant', 'competition', 'number', 'registration_date')
    list_filter = ('competition', 'registration_date')
    search_fields = ('participant__name', 'competition__name')
    date_hierarchy = 'registration_date'
