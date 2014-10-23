from dimagi.utils.couch.database import iter_docs
from dimagi.utils.decorators.memoized import memoized
from corehq.apps.locations.models import Location
from corehq.apps.commtrack.models import Product, SupplyPointCase, StockState
from corehq.apps.domain.models import Domain
from dimagi.utils.couch.loosechange import map_reduce
from corehq.apps.reports.api import ReportDataSource
from datetime import datetime, timedelta
from casexml.apps.stock.models import StockTransaction
from couchforms.models import XFormInstance
from corehq.apps.reports.commtrack.util import get_relevant_supply_point_ids, product_ids_filtered_by_program
from corehq.apps.reports.commtrack.const import STOCK_SECTION_TYPE
from casexml.apps.stock.utils import months_of_stock_remaining, stock_category
from corehq.apps.reports.standard.monitoring import MultiFormDrilldownMixin
from decimal import Decimal


class CommtrackDataSourceMixin(object):

    @property
    def domain(self):
        return self.config.get('domain')

    @property
    @memoized
    def active_location(self):
        return Location.get_in_domain(self.domain, self.config.get('location_id'))

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
        return self.config.get('startdate') or (datetime.now() - timedelta(30)).date()

    @property
    def end_date(self):
        return self.config.get('enddate') or datetime.now().date()

    @property
    def request(self):
        request = self.config.get('request')
        if request:
            return request



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

    @property
    @memoized
    def _slug_attrib_map(self):
        @memoized
        def product_name(product_id):
            return Product.get(product_id).name
        @memoized
        def supply_point_location(case_id):
            return SupplyPointCase.get(case_id).location_[-1]

        raw_map = {
            self.SLUG_PRODUCT_NAME: lambda s: product_name(s.product_id),
            self.SLUG_PRODUCT_ID: 'product_id',
            self.SLUG_LOCATION_ID: lambda s: supply_point_location(s.case_id),
            # SLUG_LOCATION_LINEAGE: lambda p: list(reversed(p.location_[:-1])),
            self.SLUG_CURRENT_STOCK: 'stock_on_hand',
            self.SLUG_CONSUMPTION: lambda s: s.get_monthly_consumption(),
            self.SLUG_MONTHS_REMAINING: 'months_remaining',
            self.SLUG_CATEGORY: 'stock_category',
            # SLUG_STOCKOUT_SINCE: 'stocked_out_since',
            # SLUG_STOCKOUT_DURATION: 'stockout_duration_in_months',
            self.SLUG_LAST_REPORTED: 'last_modified_date',
            self.SLUG_RESUPPLY_QUANTITY_NEEDED: 'resupply_quantity_needed',
        }

        # normalize the slug attrib map so everything is callable
        def _normalize_row(slug, function_or_property):
            if not callable(function_or_property):
                function = lambda s: getattr(s, function_or_property, '')
            else:
                function = function_or_property

            return slug, function

        return dict(_normalize_row(k, v) for k, v in raw_map.items())

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

        stock_states = StockState.include_archived.filter(
            section_id=STOCK_SECTION_TYPE,
            last_modified_date__lte=self.end_date,
            last_modified_date__gte=self.start_date,
        )

        if not self.config.get('archived_products', False):
            stock_states = stock_states.exclude(
                sql_product__is_archived=True
            )

        if len(sp_ids) == 1:
            stock_states = stock_states.filter(
                case_id=sp_ids[0],
            )

            if self.program_id:
                stock_states = self.filter_by_program(stock_states)

            return self.leaf_node_data(stock_states)
        else:
            stock_states = stock_states.filter(
                case_id__in=sp_ids,
            )

            if self.program_id:
                stock_states = self.filter_by_program(stock_states)

            if self.config.get('aggregate'):
                return self.aggregated_data(stock_states)
            else:
                return self.raw_product_states(stock_states, slugs)

    def format_decimal(self, d):
        # https://docs.python.org/2/library/decimal.html#decimal-faq
        if d is not None:
            return d.quantize(Decimal(1)) if d == d.to_integral() else d.normalize()
        else:
            return None

    def leaf_node_data(self, stock_states):
        for state in stock_states:
            product = Product.get(state.product_id)
            yield {
                'category': state.stock_category,
                'product_id': product._id,
                'consumption': state.get_monthly_consumption(),
                'months_remaining': state.months_remaining,
                'location_id': SupplyPointCase.get(state.case_id).location_id,
                'product_name': product.name,
                'current_stock': self.format_decimal(state.stock_on_hand),
                'location_lineage': None,
                'resupply_quantity_needed': state.resupply_quantity_needed
            }

    def aggregated_data(self, stock_states):
        product_aggregation = {}
        for state in stock_states:
            if state.product_id in product_aggregation:
                product = product_aggregation[state.product_id]
                product['current_stock'] = self.format_decimal(
                    product['current_stock'] + state.stock_on_hand
                )

                consumption = state.get_monthly_consumption()
                if product['consumption'] is None:
                    product['consumption'] = consumption
                elif consumption is not None:
                    product['consumption'] += consumption

                product['count'] += 1

                product['category'] = stock_category(
                    product['current_stock'],
                    product['consumption'],
                    Domain.get_by_name(self.domain)
                )
                product['months_remaining'] = months_of_stock_remaining(
                    product['current_stock'],
                    product['consumption']
                )
            else:
                product = Product.get(state.product_id)
                consumption = state.get_monthly_consumption()

                product_aggregation[state.product_id] = {
                    'product_id': product._id,
                    'location_id': None,
                    'product_name': product.name,
                    'location_lineage': None,
                    'resupply_quantity_needed': None,
                    'current_stock': self.format_decimal(state.stock_on_hand),
                    'count': 1,
                    'consumption': consumption,
                    'category': stock_category(
                        state.stock_on_hand,
                        consumption,
                        Domain.get_by_name(self.domain)
                    ),
                    'months_remaining': months_of_stock_remaining(
                        state.stock_on_hand,
                        consumption
                    )
                }

        return product_aggregation.values()

    def raw_product_states(self, stock_states, slugs):
        for state in stock_states:
            yield {
                slug: f(state) for slug, f in self._slug_attrib_map.items() if not slugs or slug in slugs
            }


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


class ReportingStatusDataSource(ReportDataSource, CommtrackDataSourceMixin, MultiFormDrilldownMixin):
    """
    Config:
        domain: The domain to report on.
        location_id: ID of location to get data for. Omit for all locations.
    """

    def get_data(self):
        # todo: this will probably have to paginate eventually
        if self.all_relevant_forms:
            sp_ids = get_relevant_supply_point_ids(
                self.domain,
                self.active_location,
            )

            supply_points = (SupplyPointCase.wrap(doc) for doc in iter_docs(SupplyPointCase.get_db(), sp_ids))
            form_xmlnses = [form['xmlns'] for form in self.all_relevant_forms.values()]

            for supply_point in supply_points:
                # todo: get locations in bulk
                loc = supply_point.location
                transactions = StockTransaction.objects.filter(
                    case_id=supply_point._id,
                ).exclude(
                    report__date__lte=self.start_date
                ).exclude(
                    report__date__gte=self.end_date
                ).order_by('-report__date')
                matched = False
                for trans in transactions:
                    if XFormInstance.get(trans.report.form_id).xmlns in form_xmlnses:
                        yield {
                            'loc_id': loc._id,
                            'loc_path': loc.path,
                            'name': loc.name,
                            'type': loc.location_type,
                            'reporting_status': 'reporting',
                            'geo': loc._geopoint,
                        }
                        matched = True
                        break
                if not matched:
                    yield {
                        'loc_id': loc._id,
                        'loc_path': loc.path,
                        'name': loc.name,
                        'type': loc.location_type,
                        'reporting_status': 'nonreporting',
                        'geo': loc._geopoint,
                    }
