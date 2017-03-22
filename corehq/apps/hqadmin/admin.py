from django.contrib import admin
from .models import *


class PillowCheckpointSeqStoreAdmin(admin.ModelAdmin):

    model = PillowCheckpointSeqStore
    list_display = [
        'checkpoint_id',
        'date_updated',
        'seq',
    ]


class ESRestorePillowCheckpointsAdmin(admin.ModelAdmin):

    model = ESRestorePillowCheckpoints
    list_display = [
        'checkpoint_id',
        'date_updated',
        'seq',
    ]


admin.site.register(PillowCheckpointSeqStore, PillowCheckpointSeqStoreAdmin)
admin.site.register(ESRestorePillowCheckpoints, ESRestorePillowCheckpointsAdmin)
