from django.contrib import admin
from .models import *


class SQLXFormsSessionAdmin(admin.ModelAdmin):

    model = SQLXFormsSession
    list_display = [
        'domain',
        'session_type',
        'modified_time',
        'completed',
        'user_id',
        'session_id',
        'submission_id',
        'connection_id',
    ]

    search_fields = [
        'domain',
        'user_id',
        'session_id',
        'submission_id',
        'connection_id',
    ]


admin.site.register(SQLXFormsSession, SQLXFormsSessionAdmin)
