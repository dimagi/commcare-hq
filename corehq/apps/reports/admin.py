from __future__ import absolute_import
from __future__ import unicode_literals
from django.contrib import admin

from corehq.apps.reports.models import ReportsSidebarOrdering


class ReportsSidebarOrderingAdmin(admin.ModelAdmin):
    list_display = ('domain', 'id')


admin.site.register(ReportsSidebarOrdering, ReportsSidebarOrderingAdmin)
