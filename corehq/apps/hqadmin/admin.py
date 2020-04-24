from django.contrib import admin

from corehq.apps.hqadmin.models import HistoricalPillowCheckpoint, HqDeploy


@admin.register(HistoricalPillowCheckpoint)
class ESRestorePillowCheckpointsAdmin(admin.ModelAdmin):
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


@admin.register(HqDeploy)
class HqDeployAdmin(admin.ModelAdmin):
    date_hierarchy = 'date'
    list_display = [
        'date',
        'user',
        'diff_url',
    ]
    search_fields = [
        'user',
    ]

    ordering = ['-date']
