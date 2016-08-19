from collections import namedtuple

from django.utils.translation import ugettext_lazy as _

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

    report_title = _('Zipline Warehouse - Order')
    name = _('Zipline Warehouse - Order')
    slug = 'zipline_warehouse_order'

    fields = [
        DatespanFilter,
        AsyncLocationFilter,
        EmergencyOrderStatusChoiceFilter
    ]

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
