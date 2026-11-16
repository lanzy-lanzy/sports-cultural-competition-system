from django.contrib import admin

from .models import Team, TeamMembership, TeamStaff


class TeamMembershipInline(admin.TabularInline):
    model = TeamMembership
    extra = 0
    # Event assignment uses the workspace's eligibility-aware service.
    exclude = ('events',)


class TeamStaffInline(admin.TabularInline):
    model = TeamStaff
    extra = 0


@admin.register(Team)
class TeamAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'category', 'status', 'created_at')
    list_filter = ('category', 'status')
    search_fields = ('code', 'name')
    inlines = (TeamStaffInline, TeamMembershipInline)
