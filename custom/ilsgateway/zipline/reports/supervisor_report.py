from collections import namedtuple

from django.utils.translation import ugettext as _

from corehq.apps.reports.datatables import DataTablesHeader, DataTablesColumn
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
    def headers(self):
        return DataTablesHeader(
            DataTablesColumn('date', help_text=_('timestamp for receipt of incoming emg request, automatic')),
            DataTablesColumn('location code', help_text=_('the location that corresponds to the health facility')),
            DataTablesColumn('status', help_text=_('current status of the transaction (rejected, cancelled, '
                                                   'cancelled by user, received, approved, dispatched, delivered, '
                                                   'confirmed)')),
            DataTablesColumn('total delivery time', help_text=_('time between emg status and rec status, '
                                                                'total time to resupply  in minutes')),
            DataTablesColumn('confirmation timestamp', help_text=_('timestamp for receipt of rec confirmation')),
            DataTablesColumn('emergency order request', help_text=_('structured string with product long codes'
                                                                    ' (for example, 10010203MD) and quantities'
                                                                    ' for products requested in emg request ')),
            DataTablesColumn('delivered products cost', help_text=_('value of products dropped to the'
                                                                    ' health facility, tanzanian shillings')),
            DataTablesColumn('products requested and not confirmed',
                             help_text=_('structured string with products '
                                         'that were not confirmed based on the request'))
        )

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
