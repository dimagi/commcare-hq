from collections import namedtuple

from django.utils.translation import ugettext_lazy as _

from corehq.apps.reports.filters.dates import DatespanFilter
from corehq.apps.reports.filters.fixtures import AsyncLocationFilter
from custom.ilsgateway.zipline.data_sources.supervisor_report_data_source import SupervisorReportDataSource
from custom.ilsgateway.zipline.filters import EmergencyOrderStatusChoiceFilter, OrderIdFilter
from custom.ilsgateway.zipline.reports.zipline_report import ZiplineReport

ReportConfig = namedtuple(
    'ReportConfig', ['domain', 'start_date', 'end_date', 'location_id', 'statuses', 'order_id']
)


class SupervisorReport(ZiplineReport):

    report_title = _('Supervisor Report')
    name = _('Supervisor Report')
    slug = 'supervisor_report'

    fields = [
        DatespanFilter,
        AsyncLocationFilter,
        EmergencyOrderStatusChoiceFilter,
        OrderIdFilter
    ]

    @property
    def order_id(self):
        value = self.request.GET.get('order_id')
        if not value:
            return None

        try:
            return int(value)
        except ValueError:
            return None

    @property
    def report_config(self):
        return ReportConfig(
            domain=self.domain,
            start_date=self.datespan.startdate,
            end_date=self.datespan.end_of_end_day,
            location_id=self.location_id,
            statuses=self.statuses,
            order_id=self.order_id
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
            dict(name='statuses', value=self.statuses),
            dict(name='order_id', value=self.order_id)
        ]
