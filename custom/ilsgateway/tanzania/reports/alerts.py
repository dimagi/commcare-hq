from django.shortcuts import get_object_or_404

from corehq.apps.locations.models import SQLLocation
from corehq.apps.reports.datatables import DataTablesHeader, DataTablesColumn
from corehq.apps.reports.filters.fixtures import AsyncLocationFilter
from corehq.apps.reports.generic import GenericTabularReport
from corehq.apps.reports.standard import CustomProjectReport, ProjectReportParametersMixin
from couchexport.models import Format
from custom.ilsgateway.filters import ILSDateFilter
from custom.ilsgateway.models import Alert
from custom.ilsgateway.tanzania import MonthQuarterYearMixin


class AlertReport(GenericTabularReport, CustomProjectReport, ProjectReportParametersMixin, MonthQuarterYearMixin):
    slug = 'alerts'
    fields = [AsyncLocationFilter, ILSDateFilter]
    name = 'Alerts'
    default_rows = 25
    exportable = True
    base_template = 'ilsgateway/base_template.html'

    @property
    def sql_location(self):
        location_id = self.request.GET.get('location_id')
        if location_id:
            return get_object_or_404(SQLLocation, location_id=location_id, domain=self.domain)
        return get_object_or_404(SQLLocation, location_type__name='MOHSW', domain=self.domain)

    @property
    def headers(self):
        return DataTablesHeader(*[DataTablesColumn('Alerts')])

    @property
    def rows(self):
        end_date = self.datespan.enddate
        sql_location = self.sql_location
        alerts = Alert.objects.filter(
            location_id__in=sql_location.get_descendants(include_self=True).filter(
                location_type__administrative=False,
                is_archived=False
            ).values_list('location_id'),
            date__lte=end_date,
            expires__lte=end_date
        ).order_by('-id')
        return set(alerts.values_list('text'))

    @property
    def export_table(self):
        self.export_format_override = self.export_format_override = self.request.GET.get('format', Format.XLS)
        return super(AlertReport, self).export_table
