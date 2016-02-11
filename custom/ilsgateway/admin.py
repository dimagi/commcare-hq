from django.contrib import admin

from custom.ilsgateway.models import ReportRun


class ReportRunAdmin(admin.ModelAdmin):
    list_filter = ('domain', )

admin.site.register(ReportRun, ReportRunAdmin)
