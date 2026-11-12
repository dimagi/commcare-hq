from django.contrib import admin

from corehq.apps.hqadmin.models import (
    HistoricalPillowCheckpoint,
    HqDeploy,
    PlatformDeactivationLog,
)


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


@admin.register(PlatformDeactivationLog)
class PlatformDeactivationLogAdmin(admin.ModelAdmin):
    date_hierarchy = 'created_on'
    list_display = [
        'created_on',
        'target_email',
        'platform',
        'succeeded',
        'performed_by',
    ]
    list_filter = [
        'platform',
        'succeeded',
    ]
    search_fields = [
        'target_email',
        'performed_by',
    ]

    ordering = ['-created_on']

    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
