from __future__ import absolute_import
from __future__ import unicode_literals
from django.contrib import admin

from corehq.apps.hqadmin.models import HistoricalPillowCheckpoint


class ESRestorePillowCheckpointsAdmin(admin.ModelAdmin):

    model = HistoricalPillowCheckpoint
    list_display = [
        'checkpoint_id',
        'date_updated',
        'seq',
        'seq_int',
    ]
    search_fields = [
        'checkpoint_id',
    ]

    ordering = ['-date_updated']


admin.site.register(HistoricalPillowCheckpoint, ESRestorePillowCheckpointsAdmin)
