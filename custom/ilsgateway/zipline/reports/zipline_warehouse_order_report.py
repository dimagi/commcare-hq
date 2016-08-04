from collections import namedtuple

from django.utils.translation import ugettext as _

from corehq.apps.reports.datatables import DataTablesHeader, DataTablesColumn
from corehq.apps.reports.filters.dates import DatespanFilter
from corehq.apps.reports.filters.fixtures import AsyncLocationFilter
from custom.ilsgateway.zipline.data_sources.zipline_warehouse_order_data_source import \
    ZiplineWarehouseOrderDataSource
from custom.ilsgateway.zipline.filters import EmergencyOrderStatusChoiceFilter
from custom.ilsgateway.zipline.reports.zipline_report import ZiplineReport

ReportConfig = namedtuple(
    'ReportConfig', ['domain', 'start_date', 'end_date', 'location_id', 'statuses']
)


class ZiplineWarehouseOrderReport(ZiplineReport):

    report_title = 'Zipline Warehouse - Order'
    name = 'Zipline Warehouse - Order'
    slug = 'zipline_warehouse_order'

    fields = [
        DatespanFilter,
        AsyncLocationFilter,
        EmergencyOrderStatusChoiceFilter
    ]

    @property
    def headers(self):
        return DataTablesHeader(
            DataTablesColumn('order id', help_text=_('unique identifier for each order assigned by ILSGateway')),
            DataTablesColumn('phone number', help_text=_('phone number that submitted the emg request')),
            DataTablesColumn('date', help_text=_('timestamp for receipt of incoming emg request, automatic')),
            DataTablesColumn('location code', help_text=_('the location that corresponds to the health facility')),
            DataTablesColumn('status', help_text=_('current status of the transaction (rejected, cancelled, '
                                                   'cancelled by user, received, approved, dispatched, delivered, '
                                                   'confirmed)')),
            DataTablesColumn('delivery lead time', help_text=_('time between Request to Zipline and delivery '
                                                               'completed, in minutes (Time for zipline '
                                                               'to get request and then to deliver)')),
            DataTablesColumn('Request Attempts', help_text=_('the number of times ILS gateway '
                                                             'tried to submit a request to the zipline API')),
            DataTablesColumn('status.received', help_text=_('timestamp of received status '
                                                            '(request forwarded to zipline)')),
            DataTablesColumn('status.rejected', help_text=_('timestamp of rejected status '
                                                            '(request forwarded to zipline and zipline rejects)')),
            DataTablesColumn('status.cancelled', help_text=_('timestamp from Zipine status update '
                                                             'if request is closed (cancelled) at level 3. ')),
            DataTablesColumn('status.approved', help_text=_('timestamp for approval of emg '
                                                            'request by Zipline warehouse, automated')),
            DataTablesColumn('status.dispatched', help_text=_('timestamp of dispatch of first vehicle')),
            DataTablesColumn('status.delivered', help_text=_('time stamp for delivery of final vehicle')),
            DataTablesColumn('products requested', help_text=_('structured string with product long codes '
                                                               '(for example, 10010203MD) and quantities '
                                                               'for products requested in emg request ')),
            DataTablesColumn('products delivered', help_text=_('structured string with product '
                                                               'codes for products delivered by zipline')),
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
            statuses=self.statuses
        )

    @property
    def data_source(self):
        return ZiplineWarehouseOrderDataSource(self.report_config)

    @property
    def shared_pagination_GET_params(self):
        return [
            dict(name='startdate', value=self.datespan.startdate_display),
            dict(name='enddate', value=self.datespan.enddate_display),
            dict(name='location_id', value=self.location_id),
            dict(name='statuses', value=self.statuses)
        ]
