from __future__ import absolute_import
from __future__ import unicode_literals
from django.contrib import admin
from .models import *


class UnfinishedSubmissionStubAdmin(admin.ModelAdmin):

    model = UnfinishedSubmissionStub
    list_display = [
        'xform_id',
        'timestamp',
        'saved',
        'domain',
        'date_queued',
        'attempts',
    ]

    search_fields = [
        'xform_id',
        'domain',
    ]

    list_filter = [
        'timestamp',
        'saved',
        'domain',
        'date_queued',
        'attempts',
    ]


admin.site.register(UnfinishedSubmissionStub, UnfinishedSubmissionStubAdmin)
