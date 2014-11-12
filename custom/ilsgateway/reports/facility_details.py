from corehq.apps.commtrack.models import SQLProduct, StockState
from corehq.apps.locations.models import SQLLocation
from corehq.apps.reports.datatables import DataTablesHeader, DataTablesColumn
from corehq.apps.reports.filters.fixtures import AsyncLocationFilter
from custom.ilsgateway.reports import ILSData
from custom.ilsgateway.reports.base_report import MultiReport
from dimagi.utils.decorators.memoized import memoized
from django.utils.translation import ugettext as _


def decimal_format(value):
    if value == 0:
        return '<span class="icon-remove" style="color:red"/> %.0f' % value
    elif not value:
        return '<span style="color:grey"/> No Data'
    else:
        return '%.0f' % value


def float_format(value):
    if value == 0:
        return '<span class="icon-remove" style="color:red"/> %.2f' % value
    elif not value:
        return '<span style="color:grey">No Data</span>'
    else:
        return '%.2f' % value


class InventoryHistoryData(ILSData):

    title = 'Inventory History'
    slug = 'inventory_history'
    show_chart = False
    show_table = True

    @property
    def subtitle(self):
        return 'test'

    @property
    def headers(self):
        headers = DataTablesHeader(*[
            DataTablesColumn(_('Product')),
            DataTablesColumn(_('Stock on Hand')),
            DataTablesColumn(_('Months of stock'))
        ])
        return headers

    @property
    def rows(self):
        rows = []
        if self.config['location_id']:
            sp = SQLLocation.objects.get(location_id=self.config['location_id']).supply_point_id
            ss = StockState.objects.filter(sql_product__is_archived=False, case_id=sp)
            for stock in ss:
                def calculate_months_remaining(stock_state, quantity):
                    consumption = stock_state.get_monthly_consumption()
                    if consumption is not None and consumption > 0 \
                      and quantity is not None:
                        return float(quantity) / float(consumption)
                    elif quantity == 0:
                        return 0
                    return None
                rows.append([stock.sql_product.name, decimal_format(stock.stock_on_hand),
                             float_format(calculate_months_remaining(stock, stock.stock_on_hand))])
        return rows


class FacilityDetailsReport(MultiReport):

    title = "Facility Details Report"
    fields = [AsyncLocationFilter]
    name = "Facility Details"
    slug = 'facility_details'
    use_datatables = True

    @property
    @memoized
    def data_providers(self):
        config = self.report_config
        return [InventoryHistoryData(config=config)]