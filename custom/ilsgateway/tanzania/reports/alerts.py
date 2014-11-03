from datetime import datetime, timedelta
from corehq.apps.reports.datatables import DataTablesHeader, DataTablesColumn
from corehq.apps.reports.filters.fixtures import AsyncLocationFilter
from corehq.apps.reports.filters.select import MonthFilter, YearFilter
from corehq.apps.reports.generic import GenericTabularReport
from corehq.apps.reports.standard import CustomProjectReport, ProjectReportParametersMixin, DatespanMixin
from custom.ilsgateway.models import Alert


class AlertReport(GenericTabularReport, CustomProjectReport, ProjectReportParametersMixin, DatespanMixin):
    slug = 'alerts'
    fields = [AsyncLocationFilter, MonthFilter, YearFilter]
    name = 'Alerts'
    default_rows = 25

    @property
    def headers(self):
        return DataTablesHeader(*[DataTablesColumn('Alerts')])

    @property
    def rows(self):
        month = int(self.request.GET.get('month', datetime.utcnow().month))
        year = int(self.request.GET.get('year', datetime.utcnow().year))
        begin_date = datetime(year=year, month=month, day=1)
        end_date = (begin_date + timedelta(days=32)).replace(day=1) - timedelta(seconds=1)
        alerts = Alert.objects.filter(
            supply_point=self.request.GET.get('location_id', ''),
            date__lte=end_date,
            expires__lte=end_date
        ).order_by('-id')
        return alerts.values_list('text')
