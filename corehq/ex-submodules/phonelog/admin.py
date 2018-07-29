from __future__ import absolute_import
from __future__ import unicode_literals
from django.contrib import admin
from django.core.paginator import Paginator
from django.utils.functional import cached_property
from .models import DeviceReportEntry, UserErrorEntry, UserEntry, ForceCloseEntry


class TableIsTooBigPaginator(Paginator):
    @cached_property
    def count(self):
        # This is supposed to return the matching count, but that's wicked slow
        # for massive tables, so just pick a big number
        return 10000


class DeviceReportEntryAdmin(admin.ModelAdmin):
    model = DeviceReportEntry
    paginator = TableIsTooBigPaginator
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
