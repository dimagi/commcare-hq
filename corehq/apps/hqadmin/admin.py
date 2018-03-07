from __future__ import absolute_import
from __future__ import unicode_literals
from django.contrib import admin
from .models import *


class ESRestorePillowCheckpointsAdmin(admin.ModelAdmin):

    model = HistoricalPillowCheckpoint
    list_display = [
        'checkpoint_id',
        'date_updated',
        'seq',
        'seq_int',
    ]


admin.site.register(HistoricalPillowCheckpoint, ESRestorePillowCheckpointsAdmin)
