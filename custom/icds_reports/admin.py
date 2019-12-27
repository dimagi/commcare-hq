from django.contrib import admin

from custom.icds_reports.models import AggregateSQLProfile
from custom.icds_reports.models.util import UcrReconciliationStatus
from custom.icds_reports.tasks import reconcile_data_not_in_ucr


@admin.register(AggregateSQLProfile)
class AggregateSQLProfileAdmin(admin.ModelAdmin):
    list_display = ('name', 'date', 'duration')
    list_filter = ('name', 'date')


class VerifiedListFilter(admin.SimpleListFilter):
    title = 'Verified'
    parameter_name = 'verified'

    def lookups(self, request, model_admin):
        return (
            ('verified', 'Verified to have been fully processed'),
            ('not_verified', 'Not verified to have been processed'),
        )

    def queryset(self, request, queryset):
        if self.value() == 'verified':
            return queryset.filter(verified_date__isnull=False)
        elif self.value() == 'not_verified':
            return queryset.filter(verified_date__isnull=True)


@admin.register(UcrReconciliationStatus)
class UcrReconciliationStatusAdmin(admin.ModelAdmin):
    list_display = ('db_alias', 'day', 'table_id', 'last_processed_date', 'verified_date')
    list_filter = ('db_alias', 'day', 'table_id', VerifiedListFilter)
    actions = ['queue_reconciliation']

    def queue_reconciliation(self, request, queryset):
        for pk in queryset.values_list('pk', flat=True):
            reconcile_data_not_in_ucr.delay(pk)

    queue_reconciliation.short_description = "Queue reconciliation task(s)"
