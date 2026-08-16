from django.contrib import admin
from .models import Competition, Round, Criterion


@admin.register(Competition)
class CompetitionAdmin(admin.ModelAdmin):
    list_display = ('name', 'start_date', 'end_date', 'status', 'created_by')
    list_filter = ('status', 'created_at')
    search_fields = ('name', 'description')
    date_hierarchy = 'start_date'


@admin.register(Round)
class RoundAdmin(admin.ModelAdmin):
    list_display = ('competition', 'name', 'order', 'status', 'weight_percentage')
    list_filter = ('status', 'competition')
    search_fields = ('name', 'description')
    ordering = ('competition', 'order')


@admin.register(Criterion)
class CriterionAdmin(admin.ModelAdmin):
    list_display = ('name', 'round', 'max_score',)
    list_filter = ('round',)
    search_fields = ('name', 'description')
