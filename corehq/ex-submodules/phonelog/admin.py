from django.contrib import admin
from .models import *


class DeviceReportEntryAdmin(admin.ModelAdmin):

    model = DeviceReportEntry
    list_display = [
        'xform_id',
        'msg',
        'type',
        'domain',
        'date',
        'username',
    ]

    search_fields = [
        'xform_id',
        'msg',
        'type',
        'domain',
        'date',
        'username',
    ]


admin.site.register(DeviceReportEntry, DeviceReportEntryAdmin)
admin.site.register(UserEntry)
