from django.contrib import admin

from corehq.apps.reports.models import TableauServer, TableauVisualization


admin.site.register(TableauServer)
admin.site.register(TableauVisualization)
