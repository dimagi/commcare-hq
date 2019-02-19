from __future__ import absolute_import
from __future__ import unicode_literals

from django.contrib import admin

from custom.icds_reports.models import AggregateSQLProfile


class AggregateSQLProfileAdmin(admin.ModelAdmin):
    model = AggregateSQLProfile
    list_display = ('name', 'date', 'duration')
    list_filter = ('name', 'date')


admin.site.register(AggregateSQLProfile, AggregateSQLProfileAdmin)
