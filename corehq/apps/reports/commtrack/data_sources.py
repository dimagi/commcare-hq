from corehq.apps.commtrack.util import num_periods_late
from dimagi.utils.decorators.memoized import memoized
from corehq.apps.locations.models import Location
from corehq.apps.commtrack.models import Product, SupplyPointProductCase as SPPCase
from dimagi.utils.couch.loosechange import map_reduce
from corehq.apps.reports.api import ReportDataSource
from datetime import datetime
from corehq.apps.locations.models import all_locations
from casexml.apps.stock.models import StockState
from django.db.models import Sum, Avg
from corehq.apps.reports.commtrack.util import get_relevant_supply_point_ids
from casexml.apps.stock.utils import months_of_stock_remaining, stock_category

# TODO make settings
REPORTING_PERIOD = 'weekly'
REPORTING_PERIOD_ARGS = (1,)


def is_timely(case, limit=0):
    return num_periods_late(case, REPORTING_PERIOD, *REPORTING_PERIOD_ARGS) <= limit

def reporting_status(case, start_date, end_date):
    last_reported = case.get_last_reported_date()
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

    @property
    def end_date(self):
        date = self.config.get('end_date')
        if date:
            return datetime.strptime(date, '%Y-%m-%d').date()


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
        category: The status category. See corehq.apps.commtrack.models.SupplyPointProductCase#stock_category

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
    _slug_attrib_map = {
        SLUG_PRODUCT_NAME: 'name',
        SLUG_PRODUCT_ID: 'product',
        SLUG_LOCATION_ID: lambda p: p.location_[-1],
        SLUG_LOCATION_LINEAGE: lambda p: list(reversed(p.location_[:-1])),
        SLUG_CURRENT_STOCK: 'current_stock_level',
        SLUG_CONSUMPTION: 'monthly_consumption',
        SLUG_MONTHS_REMAINING: 'months_until_stockout',
        SLUG_CATEGORY: 'current_stock_category',
        SLUG_STOCKOUT_SINCE: 'stocked_out_since',
        SLUG_STOCKOUT_DURATION: 'stockout_duration_in_months',
        SLUG_LAST_REPORTED: 'last_reported',
    }

    def slugs(self):
        return self._slug_attrib_map.keys()

    def get_data(self, slugs=None):
        sp_ids = get_relevant_supply_point_ids(self.domain, self.active_location)

        if len(sp_ids) == 1:
            stock_states = StockState.objects.filter(case_id=sp_ids[0])
            return self.leaf_node_data(stock_states)
        else:
            stock_states = StockState.objects.filter(case_id__in=sp_ids).values('product_id').annotate(
                avg_consumption=Avg('daily_consumption'),
                total_stock=Sum('stock_on_hand')
            )
            return self.aggregated_data(stock_states)

        # TODO still need to support programs
        # if self.program_id:
        #    product_cases = filter(lambda c: Product.get(c.product).program_id == self.program_id, product_cases)

    def leaf_node_data(self, stock_states):
        for state in stock_states:
            product = Product.get(state.product_id)
            yield {
                'category': state.stock_category(),
                'product_id': product._id,
                'consumption': state.daily_consumption,
                'months_remaining': state.months_remaining(),
                'location_id': state.case_id,
                'product_name': product.name,
                'current_stock': state.stock_on_hand,
                'location_lineage': None
            }

    def aggregated_data(self, stock_states):
        for state in stock_states:
            product = Product.get(state['product_id'])
            yield {
                'category': stock_category(state['total_stock'], state['avg_consumption']),
                'product_id': product._id,
                'consumption': state['avg_consumption'],
                'months_remaining': months_of_stock_remaining(state['total_stock'], state['avg_consumption']),
                'location_id': None,
                'product_name': product.name,
                'current_stock': state['total_stock'],
                'location_lineage': None
            }


    def raw_cases(self, product_cases, slugs):
        def _slug_attrib(slug, attrib, product, output):
            if not slugs or slug in slugs:
                if callable(attrib):
                    output[slug] = attrib(product)
                else:
                    output[slug] = getattr(product, attrib, '')

        for product in product_cases:
            out = {}
            for slug, attrib in self._slug_attrib_map.items():
                _slug_attrib(slug, attrib, product, out)

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
        startkey = [self.domain, self.active_location._id if self.active_location else None]
        product_cases = SPPCase.view('commtrack/product_cases',
                                     startkey=startkey,
                                     endkey=startkey + [{}],
                                     include_docs=True)
        if self.program_id:
            product_cases = filter(lambda c: Product.get(c.product).program_id == self.program_id, product_cases)
        def latest_case(cases):
            # getting last report date should probably be moved to a util function in a case wrapper class
            return max(cases, key=lambda c: c.get_last_reported_date() or datetime(2000, 1, 1).date())
        cases_by_site = map_reduce(lambda c: [(tuple(c.location_),)],
                                   lambda v: reporting_status(latest_case(v), self.start_date, self.end_date),
                                   data=product_cases, include_docs=True)

        # TODO if aggregating, won't want to fetch all these locs (will only want to fetch aggregation sites)
        locs = dict((loc._id, loc) for loc in Location.view(
                '_all_docs',
                keys=[path[-1] for path in cases_by_site.keys()],
                include_docs=True))

        for path, status in cases_by_site.iteritems():
            loc = locs[path[-1]]

            yield {
                'loc_id': loc._id,
                'loc_path': loc.path,
                'name': loc.name,
                'type': loc.location_type,
                'reporting_status': status,
                'geo': loc._geopoint,
            }

