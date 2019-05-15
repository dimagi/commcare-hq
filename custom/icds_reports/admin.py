from __future__ import absolute_import
from __future__ import unicode_literals

from django.contrib import admin

from custom.icds_reports.models import AggregateSQLProfile
from custom.icds_reports.models.util import (
    CitusDashboardDiff,
    CitusDashboardException,
    CitusDashboardTiming,
)


@admin.register(AggregateSQLProfile)
class AggregateSQLProfileAdmin(admin.ModelAdmin):
    list_display = ('name', 'date', 'duration')
    list_filter = ('name', 'date')


@admin.register(CitusDashboardException)
@admin.register(CitusDashboardDiff)
class CitusDashboardAdmin(admin.ModelAdmin):
    list_display = ('data_source', 'date_created')
    list_filter = ('data_source',)
    ordering = ('-date_created',)


@admin.register(CitusDashboardTiming)
class CitusDashboardTimingAdmin(CitusDashboardAdmin):
    list_display = ('data_source', 'control_duration', 'candidate_duration', 'date_created')
