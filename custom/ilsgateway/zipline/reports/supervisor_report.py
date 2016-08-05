from collections import namedtuple

from corehq.apps.reports.filters.dates import DatespanFilter
from corehq.apps.reports.filters.fixtures import AsyncLocationFilter
from custom.ilsgateway.zipline.data_sources.supervisor_report_data_source import SupervisorReportDataSource
from custom.ilsgateway.zipline.filters import EmergencyOrderStatusChoiceFilter, OrderIdChoiceFilter
from custom.ilsgateway.zipline.reports.zipline_report import ZiplineReport

ReportConfig = namedtuple(
    'ReportConfig', ['domain', 'start_date', 'end_date', 'location_id', 'statuses', 'orders_id']
)


class SupervisorReport(ZiplineReport):

    report_title = 'Supervisor Report'
    name = 'Supervisor Report'
    slug = 'supervisor_report'

    fields = [
        DatespanFilter,
        AsyncLocationFilter,
        EmergencyOrderStatusChoiceFilter,
        OrderIdChoiceFilter
    ]

    @property
    def orders_id(self):
        return self.request.GET.getlist('orders_id')

    @property
    def report_config(self):
        return ReportConfig(
            domain=self.domain,
            start_date=self.datespan.startdate,
            end_date=self.datespan.end_of_end_day,
            location_id=self.location_id,
            statuses=self.statuses,
            orders_id=self.orders_id
        )

    @property
    def data_source(self):
        return SupervisorReportDataSource(self.report_config)

    @property
    def shared_pagination_GET_params(self):
        return [
            dict(name='startdate', value=self.datespan.startdate_display),
            dict(name='enddate', value=self.datespan.enddate_display),
            dict(name='location_id', value=self.location_id),
            dict(name='statuses', value=self.statuses)
        ]
