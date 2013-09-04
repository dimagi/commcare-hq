from corehq.apps.commtrack.util import supply_point_type_categories, num_periods_late
from dimagi.utils.decorators.memoized import memoized
from corehq.apps.locations.models import Location
from corehq.apps.commtrack.models import Product, SupplyPointProductCase as SPPCase
from dimagi.utils.couch.loosechange import map_reduce
from corehq.apps.reports.api import ReportDataSource
import corehq.apps.locations.util as loc_util


# TODO make settings
REPORTING_PERIOD = 'weekly'
REPORTING_PERIOD_ARGS = (1,)


def is_timely(case, limit=0):
    return num_periods_late(case, REPORTING_PERIOD, *REPORTING_PERIOD_ARGS) <= limit


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

    SLUG_CATEGORY = 'category'
    _slug_attrib_map = {
        SLUG_PRODUCT_NAME: 'name',
        SLUG_PRODUCT_ID: 'product',
        SLUG_LOCATION_ID: lambda p: p.location_[-1],
        SLUG_LOCATION_LINEAGE: lambda p: list(reversed(p.location_[:-1])),
        SLUG_CURRENT_STOCK: 'current_stock_level',
        SLUG_CONSUMPTION: 'monthly_consumption',
        SLUG_MONTHS_REMAINING: 'months_until_stockout',
        SLUG_CATEGORY: 'current_stock_category'
    }

    def slugs(self):
        return self._slug_attrib_map.keys()

    def get_data(self, slugs=None):
        startkey = [self.domain, self.active_location._id if self.active_location else None]
        if self.active_product:
            startkey.append(self.active_product['_id'])

        product_cases = SPPCase.view('commtrack/product_cases', startkey=startkey, endkey=startkey + [{}], include_docs=True)

        if self.config.get('aggregate'):
            return self.aggregate_cases(product_cases, slugs)
        else:
            return self.raw_cases(product_cases, slugs)

    def raw_cases(self, product_cases, slugs):
        def _slug_attrib(slug, attrib, product, output):
            if not slugs or slug in slugs:
                if callable(attrib):
                    output[slug] = attrib(product)
                else:
                    output[slug] = getattr(product, attrib)

        for product in product_cases:
            out = {}
            for slug, attrib in self._slug_attrib_map.items():
                _slug_attrib(slug, attrib, product, out)

            yield out

    def aggregate_cases(self, product_cases, slugs):
        cases_by_product = map_reduce(lambda c: [(c.product,)], data=product_cases, include_docs=True)
        products = Product.view('_all_docs', keys=cases_by_product.keys(), include_docs=True)

        def _sum(vals):
            return sum(vals) if vals else None

        def aggregate_product(cases):
            data = [(c.current_stock_level, c.monthly_consumption) for c in cases if is_timely(c, 1000)]
            total_stock = _sum([d[0] for d in data if d[0] is not None])
            total_consumption = _sum([d[1] for d in data if d[1] is not None])
            # exclude stock values w/o corresponding consumption figure from total months left calculation
            consumable_stock = _sum([d[0] for d in data if d[0] is not None and d[1] is not None])

            return {
                'total_stock': total_stock,
                'total_consumption': total_consumption,
                'consumable_stock': consumable_stock,
            }

        status_by_product = dict((p, aggregate_product(cases)) for p, cases in cases_by_product.iteritems())
        for p in sorted(products, key=lambda p: p.name):
            stats = status_by_product[p._id]

            months_left = SPPCase.months_of_stock_remaining(stats['consumable_stock'], stats['total_consumption'])
            category = SPPCase.stock_category(stats['total_stock'], stats['total_consumption'], stats['consumable_stock'])

            full_output = {
                self.SLUG_PRODUCT_NAME: p.name,
                self.SLUG_PRODUCT_ID: p._id,
                self.SLUG_LOCATION_ID: self.active_location._id if self.active_location else None,
                self.SLUG_LOCATION_LINEAGE: self.active_location.lineage if self.active_location else None,
                self.SLUG_CURRENT_STOCK: stats['total_stock'],
                self.SLUG_CONSUMPTION: stats['total_consumption'],
                self.SLUG_MONTHS_REMAINING: months_left,
                self.SLUG_CATEGORY: category,
            }

            yield dict((slug, full_output['slug']) for slug in slugs) if slugs else full_output