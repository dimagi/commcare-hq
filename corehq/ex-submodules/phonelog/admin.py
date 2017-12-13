from __future__ import absolute_import
from django.contrib import admin
from .models import DeviceReportEntry, UserErrorEntry, UserEntry, ForceCloseEntry


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
    # postgres SQL count query takes long time on big tables
    show_full_result_count = False


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


class ForceCloseEntryAdmin(admin.ModelAdmin):
    model = ForceCloseEntry
    list_display = [
        'domain',
        'server_date',
        'user_id',
        'app_id',
        'version_number',
        'msg',
        'session_readable',
    ]
    search_fields = [
        'domain',
        'user_id',
        'app_id',
        'version_number',
        'msg',
    ]


admin.site.register(DeviceReportEntry, DeviceReportEntryAdmin)
admin.site.register(UserErrorEntry, UserErrorEntryAdmin)
admin.site.register(UserEntry, UserEntryAdmin)
admin.site.register(ForceCloseEntry, ForceCloseEntryAdmin)
