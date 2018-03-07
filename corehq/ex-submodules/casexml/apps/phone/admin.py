from __future__ import absolute_import
from django.contrib import admin
from .models import *


class OwnershipCleanlinessFlagAdmin(admin.ModelAdmin):

    model = OwnershipCleanlinessFlag
    list_display = [
        'domain',
        'owner_id',
        'is_clean',
        'last_checked',
        'hint',
    ]

    search_fields = [
        'domain',
        'owner_id',
    ]

    list_filter = [
        'is_clean',
    ]


class SyncLogSQLAdmin(admin.ModelAdmin):
    model = SyncLogSQL
    list_display = ['synclog_id', 'domain', 'user_id', 'date']
    list_filter = ['domain', 'user_id', 'date']
    search_fields = ['domain', 'user_id']

admin.site.register(SyncLogSQL, SyncLogSQLAdmin)
admin.site.register(OwnershipCleanlinessFlag, OwnershipCleanlinessFlagAdmin)
