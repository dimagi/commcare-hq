from django.contrib import admin

from corehq.apps.reports.models import ReportsSidebarOrdering, TableauServer, TableauVisualization


class ReportsSidebarOrderingAdmin(admin.ModelAdmin):
    list_display = ('domain', 'id')


admin.site.register(ReportsSidebarOrdering, ReportsSidebarOrderingAdmin)


admin.site.register(TableauServer)
admin.site.register(TableauVisualization)
