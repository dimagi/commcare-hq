from django.contrib import admin

from custom.icds_reports.models import AggregateSQLProfile


@admin.register(AggregateSQLProfile)
class AggregateSQLProfileAdmin(admin.ModelAdmin):
    list_display = ('name', 'date', 'duration')
    list_filter = ('name', 'date')
