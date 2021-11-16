from django.contrib import admin
from .models import *


class SyncLogSQLAdmin(admin.ModelAdmin):
    model = SyncLogSQL
    list_display = ['synclog_id', 'domain', 'user_id', 'date']
    list_filter = ['domain', 'user_id', 'date']
    search_fields = ['domain', 'user_id']


admin.site.register(SyncLogSQL, SyncLogSQLAdmin)
