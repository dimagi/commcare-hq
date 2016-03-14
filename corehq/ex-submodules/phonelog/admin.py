from django.contrib import admin
from .models import DeviceReportEntry, UserErrorEntry, UserEntry


class DeviceReportEntryAdmin(admin.ModelAdmin):
    model = DeviceReportEntry
    list_display = [
        'domain',
        'username',
        'msg',
        'type',
        'date',
    ]
    search_fields = [
        'xform_id',
        'msg',
        'type',
        'domain',
        'date',
        'username',
    ]


class UserErrorEntryAdmin(admin.ModelAdmin):
    model = UserErrorEntry
    list_display = [
        'domain',
        'type',
        'expr',
        'msg',
        'app_id',
        'version_number',
        'date',
    ]
    search_fields = [
        'domain',
        'type',
        'expr',
        'msg',
        'app_id',
        'version_number',
        'date',
    ]


class UserEntryAdmin(admin.ModelAdmin):
    model = UserEntry
    list_display = [
        'username',
        'xform_id',
        'sync_token',
    ]
    search_fields = [
        'username',
        'xform_id',
        'sync_token',
    ]


admin.site.register(DeviceReportEntry, DeviceReportEntryAdmin)
admin.site.register(UserErrorEntry, UserErrorEntryAdmin)
admin.site.register(UserEntry, UserEntryAdmin)
