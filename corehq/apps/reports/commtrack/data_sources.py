from corehq.apps.commtrack.util import num_periods_late
from dimagi.utils.decorators.memoized import memoized
from corehq.apps.locations.models import Location
from corehq.apps.commtrack.models import Product, SupplyPointCase, StockState
from corehq.apps.domain.models import Domain
from dimagi.utils.couch.loosechange import map_reduce
from corehq.apps.reports.api import ReportDataSource
from datetime import datetime, timedelta
from casexml.apps.stock.models import StockTransaction
from django.db.models import Sum, Avg
from corehq.apps.reports.commtrack.util import get_relevant_supply_point_ids, product_ids_filtered_by_program
from corehq.apps.reports.commtrack.const import STOCK_SECTION_TYPE
from casexml.apps.stock.utils import months_of_stock_remaining, stock_category

# TODO make settings
REPORTING_PERIOD = 'weekly'
REPORTING_PERIOD_ARGS = (1,)


def is_timely(case, limit=0):
    return num_periods_late(case, REPORTING_PERIOD, *REPORTING_PERIOD_ARGS) <= limit

def reporting_status(transaction, start_date, end_date):
    if transaction:
        last_reported = transaction.report.date.date()
    else:
        last_reported = None

    if last_reported and last_reported < start_date:
        return 'ontime'
    elif last_reported and start_date <= last_reported <= end_date:
        return 'late'
    else:
        return 'nonreporting'


class CommtrackDataSourceMixin(object):

    @property
    def domain(self):
        return self.config.get('domain')

    @property
    @memoized
    def active_location(self):
        loc_id = self.config.get('location_id')
        if loc_id:
            return Location.get(loc_id)

    @property
    @memoized
    def active_product(self):
        prod_id = self.config.get('product_id')
        if prod_id:
            return Product.get(prod_id)

    @property
    @memoized
    def program_id(self):
        prog_id = self.config.get('program_id')
        if prog_id != '':
            return prog_id

    @property
    def start_date(self):
        date = self.config.get('start_date')
        if date:
            return datetime.strptime(date, '%Y-%m-%d').date()
        else:
            return (datetime.now() - timedelta(30)).date()

    @property
    def end_date(self):
        date = self.config.get('end_date')
        if date:
            return datetime.strptime(date, '%Y-%m-%d').date()
        else:
            return datetime.now().date()


class StockStatusDataSource(ReportDataSource, CommtrackDataSourceMixin):
    """
    Config:
        domain: The domain to report on.
        location_id: ID of location to get data for. Omit for all locations.
        product_id: ID of product to get data for. Omit for all products.
        aggregate: True to aggregate the indicators by product for the current location.

    Data Slugs:
        product_name: Name of the product
        product_id: ID of the product
        location_id: The ID of the current location.
        location_lineage: The lineage of the current location.
        current_stock: The current stock level
        consumption: The current monthly consumption rate
        months_remaining: The number of months remaining until stock out
        category: The status category. See casexml.apps.stock.models.StockState.stock_category
        resupply_quantity_needed: Max amount - current amount

    """
    slug = 'agg_stock_status'

    SLUG_PRODUCT_NAME = 'product_name'
    SLUG_PRODUCT_ID = 'product_id'
    SLUG_MONTHS_REMAINING = 'months_remaining'
    SLUG_CONSUMPTION = 'consumption'
    SLUG_CURRENT_STOCK = 'current_stock'
    SLUG_LOCATION_ID = 'location_id'
    SLUG_LOCATION_LINEAGE = 'location_lineage'
    SLUG_STOCKOUT_SINCE = 'stockout_since'
    SLUG_STOCKOUT_DURATION = 'stockout_duration'
    SLUG_LAST_REPORTED = 'last_reported'
    SLUG_CATEGORY = 'category'
    SLUG_RESUPPLY_QUANTITY_NEEDED = 'resupply_quantity_needed'

    _slug_attrib_map = {
        SLUG_PRODUCT_NAME: lambda s: Product.get(s.product_id).name,
        SLUG_PRODUCT_ID: lambda s: s.product_id,
        SLUG_LOCATION_ID: lambda s: SupplyPointCase.get(s.case_id).location_[-1],
        # SLUG_LOCATION_LINEAGE: lambda p: list(reversed(p.location_[:-1])),
        SLUG_CURRENT_STOCK: 'stock_on_hand',
        SLUG_CONSUMPTION: lambda s: s.daily_consumption * 30 if s.daily_consumption else None,
        SLUG_MONTHS_REMAINING: 'months_remaining',
        SLUG_CATEGORY: 'stock_category',
        # SLUG_STOCKOUT_SINCE: 'stocked_out_since',
        # SLUG_STOCKOUT_DURATION: 'stockout_duration_in_months',
        SLUG_LAST_REPORTED: 'last_modified_date',
        SLUG_RESUPPLY_QUANTITY_NEEDED: 'resupply_quantity_needed',
    }

    def slugs(self):
        return self._slug_attrib_map.keys()

    def filter_by_program(self, stock_states):
        return stock_states.filter(
            product_id__in=product_ids_filtered_by_program(
                self.domain,
                self.program_id
            )
        )

    def get_data(self, slugs=None):
        sp_ids = get_relevant_supply_point_ids(self.domain, self.active_location)

        if len(sp_ids) == 1:
            stock_states = StockState.objects.filter(
                case_id=sp_ids[0],
                section_id=STOCK_SECTION_TYPE,
                last_modified_date__lte=self.end_date,
                last_modified_date__gte=self.start_date,
            )

            if self.program_id:
                stock_states = self.filter_by_program(stock_states)

            return self.leaf_node_data(stock_states)
        else:
            stock_states = StockState.objects.filter(
                case_id__in=sp_ids,
                section_id=STOCK_SECTION_TYPE,
                last_modified_date__lte=self.end_date,
                last_modified_date__gte=self.start_date,
            )

            if self.program_id:
                stock_states = self.filter_by_program(stock_states)

            if self.config.get('aggregate'):
                aggregates = stock_states.values('product_id').annotate(
                    avg_consumption=Avg('daily_consumption'),
                    total_stock=Sum('stock_on_hand')
                )
                return self.aggregated_data(aggregates)
            else:
                return self.raw_product_states(stock_states, slugs)

    def leaf_node_data(self, stock_states):
        for state in stock_states:
            product = Product.get(state.product_id)
            yield {
                'category': state.stock_category,
                'product_id': product._id,
                'consumption': state.daily_consumption * 30 if state.daily_consumption else None,
                'months_remaining': state.months_remaining,
                'location_id': SupplyPointCase.get(state.case_id).location_id,
                'product_name': product.name,
                'current_stock': state.stock_on_hand,
                'location_lineage': None,
                'resupply_quantity_needed': state.resupply_quantity_needed
            }

    def aggregated_data(self, stock_states):
        for state in stock_states:
            product = Product.get(state['product_id'])
            yield {
                'category': stock_category(
                    state['total_stock'],
                    state['avg_consumption'],
                    Domain.get_by_name(self.domain)
                ),
                'product_id': product._id,
                'consumption': state['avg_consumption'],
                'months_remaining': months_of_stock_remaining(state['total_stock'], state['avg_consumption']),
                'location_id': None,
                'product_name': product.name,
                'current_stock': state['total_stock'],
                'location_lineage': None,
                'resupply_quantity_needed': None
            }


    def raw_product_states(self, stock_states, slugs):
        def _slug_attrib(slug, attrib, product, output):
            if not slugs or slug in slugs:
                if callable(attrib):
                    output[slug] = attrib(product)
                else:
                    output[slug] = getattr(product, attrib, '')

        for state in stock_states:
            out = {}
            for slug, attrib in self._slug_attrib_map.items():
                _slug_attrib(slug, attrib, state, out)

            yield out


class StockStatusBySupplyPointDataSource(StockStatusDataSource):
    def get_data(self):
        data = list(super(StockStatusBySupplyPointDataSource, self).get_data())

        products = dict((r['product_id'], r['product_name']) for r in data)
        product_ids = sorted(products.keys(), key=lambda e: products[e])

        by_supply_point = map_reduce(lambda e: [(e['location_id'],)], data=data, include_docs=True)
        locs = dict((loc._id, loc) for loc in Location.view(
                '_all_docs',
                keys=by_supply_point.keys(),
                include_docs=True))

        for loc_id, subcases in by_supply_point.iteritems():
            loc = locs[loc_id]
            by_product = dict((c['product_id'], c) for c in subcases)

            rec = {
                'name': loc.name,
                'type': loc.location_type,
                'geo': loc._geopoint,
            }
            for prod in product_ids:
                rec.update(dict(('%s-%s' % (prod, key), by_product.get(prod, {}).get(key)) for key in
                                ('current_stock', 'consumption', 'months_remaining', 'category')))
            yield rec

class ReportingStatusDataSource(ReportDataSource, CommtrackDataSourceMixin):
    """
    Config:
        domain: The domain to report on.
        location_id: ID of location to get data for. Omit for all locations.
    """

    def get_data(self):
        sp_ids = get_relevant_supply_point_ids(
            self.domain,
            self.active_location
        )

        products = Product.by_domain(self.domain)
        if self.program_id:
            products = filter(
                lambda product: product.program_id == self.program_id, products
            )

        for sp_id in sp_ids:
            loc = SupplyPointCase.get(sp_id).location
            transactions = StockTransaction.objects.filter(
                case_id=sp_id,
                section_id=STOCK_SECTION_TYPE,
            )

            if transactions:
                last_transaction = sorted(
                    transactions,
                    key=lambda trans: trans.report.date
                )[-1]
            else:
                last_transaction = None

            yield {
                'loc_id': loc._id,
                'loc_path': loc.path,
                'name': loc.name,
                'type': loc.location_type,
                'reporting_status': reporting_status(
                    last_transaction,
                    self.start_date,
                    self.end_date
                ),
                'geo': loc._geopoint,
            }
