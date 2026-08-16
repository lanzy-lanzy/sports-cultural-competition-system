from django.contrib import admin
from .models import Participant, ParticipantCompetition


@admin.register(Participant)
class ParticipantAdmin(admin.ModelAdmin):
    list_display = ('name', 'email', 'phone', 'status', 'registration_date')
    list_filter = ('status',)
    search_fields = ('name', 'email', 'phone')
    date_hierarchy = 'registration_date'


@admin.register(ParticipantCompetition)
class ParticipantCompetitionAdmin(admin.ModelAdmin):
    list_display = ('participant', 'competition', 'number', 'registration_date')
    list_filter = ('competition', 'registration_date')
    search_fields = ('participant__name', 'competition__name')
    date_hierarchy = 'registration_date'
