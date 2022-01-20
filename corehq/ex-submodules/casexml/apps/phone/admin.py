from django.contrib import admin
from .models import SyncLogSQL


class SyncLogSQLAdmin(admin.ModelAdmin):
    model = SyncLogSQL
    list_display = ['synclog_id', 'domain', 'user_id', 'date']
    list_filter = ['date']
    search_fields = ['domain', 'user_id', 'auth_type']


admin.site.register(SyncLogSQL, SyncLogSQLAdmin)
