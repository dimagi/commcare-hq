from corehq.apps.commtrack.models import StockState
from corehq.apps.locations.models import Location
from corehq.apps.products.models import Product
from corehq.apps.reports.commtrack.const import STOCK_SECTION_TYPE
from corehq.apps.reports.commtrack.util import get_relevant_supply_point_ids
from corehq.apps.reports.datatables import DataTablesHeader, DataTablesColumn
from corehq.apps.reports.filters.dates import DatespanFilter
from corehq.apps.reports.filters.fixtures import AsyncLocationFilter
from custom.ewsghana.filters import ProductByProgramFilter
from custom.ewsghana.reports import EWSData
from custom.ewsghana.reports.base_report import MultiReport
from dimagi.utils.decorators.memoized import memoized
from django.utils.translation import ugettext as _


class StockLevelsSubmissionData(EWSData):
    title = 'Aggregate Stock Report'
    slug = 'stock_levels_submission'
    show_table = True

    @property
    def sublocations(self):
        location = Location.get(self.config['location_id'])
        if location.children:
            return location.children
        else:
            return [location]

    @property
    def headers(self):
        headers = DataTablesHeader(*[
            DataTablesColumn(_('Location')),
            DataTablesColumn(_('Stockout')),
            DataTablesColumn(_('Low Stock')),
            DataTablesColumn(_('Adequate Stock')),
            DataTablesColumn(_('Overstock')),
            DataTablesColumn(_('Total'))])

        if self.config['product'] != '':
            headers.add_column(DataTablesColumn(_('AMC')))
        return headers

    def get_prod_data(self):

        for sublocation in self.sublocations:
            sp_ids = get_relevant_supply_point_ids(self.config['domain'], sublocation)
            stock_states = StockState.include_archived.filter(
                case_id__in=sp_ids,
                last_modified_date__lte=self.config['enddate'],
                last_modified_date__gte=self.config['startdate'],
                section_id=STOCK_SECTION_TYPE
            )

            stock_states = stock_states.order_by('product_id')
            state_grouping = {}
            for state in stock_states:
                status = state.stock_category
                if state.product_id in state_grouping:
                    state_grouping[state.product_id][status] += 1
                else:
                    state_grouping[state.product_id] = {
                        'id': state.product_id,
                        'stockout': 0,
                        'understock': 0,
                        'overstock': 0,
                        'adequate': 0,
                        'nodata': 0,
                        'facility_count': 1,
                        'amc': int(state.get_monthly_consumption() or 0)
                    }
                    state_grouping[state.product_id][status] = 1

            location_grouping = {
                'location': sublocation.name,
                'stockout': 0,
                'understock': 0,
                'adequate': 0,
                'overstock': 0,
                'total': 0,
                'amc': 0
            }
            product_ids = []
            if self.config['program'] != '' and self.config['product'] == '':
                product_ids = [product.get_id for product in Product.by_program_id(self.config['domain'],
                                                                                   self.config['program'])]
            elif self.config['program'] != '' and self.config['product'] != '':
                product_ids = [self.config['product']]
            else:
                product_ids = Product.ids_by_domain(self.config['domain'])

            for product in state_grouping.values():
                if product['id'] in product_ids:
                    location_grouping['stockout'] += product['stockout']
                    location_grouping['understock'] += product['understock']
                    location_grouping['adequate'] += product['adequate']
                    location_grouping['overstock'] += product['overstock']
                    location_grouping['total'] += sum([product['stockout'], product['understock'],
                                                       product['adequate'], product['overstock']])
                    location_grouping['amc'] += product['amc']

            location_grouping['stockout'] = self.percent_fn(location_grouping['total'],
                                                            location_grouping['stockout'])
            location_grouping['understock'] = self.percent_fn(location_grouping['total'],
                                                              location_grouping['understock'])
            location_grouping['adequate'] = self.percent_fn(location_grouping['total'],
                                                            location_grouping['adequate'])
            location_grouping['overstock'] = self.percent_fn(location_grouping['total'],
                                                             location_grouping['overstock'])

            yield location_grouping

    @property
    def rows(self):
        for location_grouping in self.get_prod_data():
            row = [location_grouping['location'],
                   location_grouping['stockout'],
                   location_grouping['understock'],
                   location_grouping['adequate'],
                   location_grouping['overstock'],
                   location_grouping['total']]
            if self.config['product'] != '':
                row.append(location_grouping['amc'])

            yield row


class StockLevelsReport(MultiReport):
    title = "Aggregate Stock Report"
    fields = [AsyncLocationFilter, ProductByProgramFilter, DatespanFilter]
    name = "Stock Levels Report"
    slug = 'ews_stock_levels_report'

    @property
    def report_config(self):

        return dict(
            domain=self.domain,
            startdate=self.datespan.startdate_utc,
            enddate=self.datespan.enddate_utc,
            location_id=self.request.GET.get('location_id'),
            program=self.request.GET.get('filter_by_program'),
            product=self.request.GET.get('filter_by_product'),
        )

    @property
    @memoized
    def data_providers(self):
        config = self.report_config
        return [StockLevelsSubmissionData(config)]
