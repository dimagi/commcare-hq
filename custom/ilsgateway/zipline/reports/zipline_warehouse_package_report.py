from collections import namedtuple

from corehq.apps.reports.filters.dates import DatespanFilter
from corehq.apps.reports.filters.fixtures import AsyncLocationFilter
from custom.ilsgateway.zipline.data_sources.zipline_warehouse_package_data_source import \
    ZiplineWarehousePackageDataSource
from custom.ilsgateway.zipline.filters import EmergencyPackageStatusChoiceFilter, OrderIdChoiceFilter
from custom.ilsgateway.zipline.reports.zipline_report import ZiplineReport


ReportConfig = namedtuple(
    'ReportConfig', ['domain', 'start_date', 'end_date', 'location_id', 'statuses', 'orders_id']
)


class ZiplineWarehousePackageReport(ZiplineReport):
    report_title = 'Zipline Warehouse - Package'
    name = 'Zipline Warehouse - Package'
    slug = 'zipline_warehouse_package'

    fields = [
        DatespanFilter,
        AsyncLocationFilter,
        EmergencyPackageStatusChoiceFilter,
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
        return ZiplineWarehousePackageDataSource(self.report_config)

    @property
    def shared_pagination_GET_params(self):
        return [
            dict(name='startdate', value=self.datespan.startdate_display),
            dict(name='enddate', value=self.datespan.enddate_display),
            dict(name='location_id', value=self.location_id),
            dict(name='statuses', value=self.statuses),
            dict(name='orders_id', value=self.orders_id)
        ]
