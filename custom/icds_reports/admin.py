from django.contrib import admin

from custom.icds_reports.models import AggregateSQLProfile
from custom.icds_reports.models.util import UcrReconciliationStatus
from custom.icds_reports.tasks import reconcile_data_not_in_ucr


@admin.register(AggregateSQLProfile)
class AggregateSQLProfileAdmin(admin.ModelAdmin):
    list_display = ('name', 'date', 'duration')
    list_filter = ('name', 'date')


@admin.register(UcrReconciliationStatus)
class UcrReconciliationStatusAdmin(admin.ModelAdmin):
    list_display = ('db_alias', 'day', 'table_id', 'verified_date')
    actions = ['queue_reconciliation']

    def queue_reconciliation(self, request, queryset):
        for pk in queryset.values_list('pk', flat=True):
            reconcile_data_not_in_ucr.delay(pk)

    queue_reconciliation.short_description = "Queue reconciliation task(s)"
