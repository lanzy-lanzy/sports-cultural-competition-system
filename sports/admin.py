from django.contrib import admin

from .models import EventEntry, Match, MatchEntry, SportsEvent, SportType, Venue


@admin.register(SportType)
class SportTypeAdmin(admin.ModelAdmin):
    list_display = ('name', 'team_based', 'is_active')
    search_fields = ('name',)


@admin.register(Venue)
class VenueAdmin(admin.ModelAdmin):
    list_display = ('name', 'location', 'capacity', 'is_active')
    search_fields = ('name', 'location')


class EventEntryInline(admin.TabularInline):
    model = EventEntry
    extra = 0


@admin.register(SportsEvent)
class SportsEventAdmin(admin.ModelAdmin):
    list_display = ('name', 'competition', 'sport_type', 'gender', 'category', 'format', 'status')
    list_filter = ('status', 'format', 'gender', 'category')
    search_fields = ('name', 'competition__name', 'sport_type__name')
    inlines = [EventEntryInline]


class MatchEntryInline(admin.TabularInline):
    model = MatchEntry
    extra = 0


@admin.register(Match)
class MatchAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'event', 'round_number', 'venue', 'scheduled_start', 'status')
    list_filter = ('status', 'round_number')
    search_fields = ('event__name', 'name')
    inlines = [MatchEntryInline]


@admin.register(EventEntry)
class EventEntryAdmin(admin.ModelAdmin):
    list_display = ('event', 'team', 'participant', 'seed', 'status')
    list_filter = ('status',)


@admin.register(MatchEntry)
class MatchEntryAdmin(admin.ModelAdmin):
    list_display = ('match', 'team', 'participant', 'side', 'score', 'is_winner')