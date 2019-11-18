from django.contrib import admin

from .models import *


class SQLXFormsSessionAdmin(admin.ModelAdmin):

    model = SQLXFormsSession
    list_display = [
        'domain',
        'session_type',
        'start_time',
        'modified_time',
        'session_is_open',
        'connection_id',
        'session_id',
        'submission_id',
    ]

    search_fields = [
        'domain',
        'session_id',
        'submission_id',
        'connection_id',
    ]

    ordering = ('-start_time',)


admin.site.register(SQLXFormsSession, SQLXFormsSessionAdmin)
