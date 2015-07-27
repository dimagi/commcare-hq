import logging
from couchdbkit.exceptions import ResourceNotFound
from dimagi.utils.couch.database import iter_docs
from dimagi.utils.decorators.memoized import memoized
from corehq.apps.locations.models import Location
from corehq.apps.commtrack.models import SupplyPointCase, StockState, SQLLocation
from corehq.apps.products.models import Product
from dimagi.utils.couch.loosechange import map_reduce
from corehq.apps.reports.api import ReportDataSource
from datetime import datetime, timedelta
from dateutil import parser
from casexml.apps.stock.models import StockTransaction, StockReport
from couchforms.models import XFormInstance
from corehq.apps.reports.commtrack.util import get_relevant_supply_point_ids, product_ids_filtered_by_program
from corehq.apps.reports.commtrack.const import STOCK_SECTION_TYPE
from casexml.apps.stock.utils import months_of_stock_remaining, stock_category, state_stock_category
from corehq.apps.reports.standard.monitoring import MultiFormDrilldownMixin
from decimal import Decimal
from django.db.models import Sum


def format_decimal(d):
    # https://docs.python.org/2/library/decimal.html#decimal-faq
    if d is not None:
        return d.quantize(Decimal(1)) if d == d.to_integral() else d.normalize()
    else:
        return None


def _location_map(location_ids):
    return {
        loc.location_id: loc
        for loc in (SQLLocation.objects
                    .filter(is_archived=False,
                            location_id__in=location_ids)
                    .prefetch_related('location_type'))
    }


def geopoint(location):
    if None in (location.latitude, location.longitude):
        return None
    return '{} {}'.format(location.latitude, location.longitude)


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
        return self.config.get('startdate') or (datetime.utcnow() - timedelta(30)).date()

    @property
    def end_date(self):
        return self.config.get('enddate') or datetime.utcnow().date()

    @property
    def request(self):
        request = self.config.get('request')
        if request:
            return request


class SimplifiedInventoryDataSource(ReportDataSource, CommtrackDataSourceMixin):
    slug = 'location_inventory'

    def datetime(self):
        """
        Returns a datetime object at the end of the selected
        (or current) date. This is needed to properly filter
        transactions that occur during the day we are filtering
        for
        """
        # note: empty string is parsed as today's date
        date = self.config.get('date', '')

        try:
            date = parser.parse(date).date()
        except ValueError:
            date = datetime.utcnow().date()

        return datetime(date.year, date.month, date.day, 23, 59, 59)

    def get_data(self, slugs=None):
        if self.active_location:
            current_location = self.active_location.sql_location

            if current_location.supply_point_id:
                locations = [current_location]
            else:
                locations = []

            locations += list(
                current_location.get_descendants().filter(
                    is_archived=False,
                    supply_point_id__isnull=False
                )
            )
        else:
            locations = SQLLocation.objects.filter(
                domain=self.domain,
                is_archived=False,
                supply_point_id__isnull=False
            )

        # locations at this point will only have location objects
        # that have supply points associated
        for loc in locations[:self.config.get('max_rows', 100)]:
            transactions = StockTransaction.objects.filter(
                case_id=loc.supply_point_id,
            )

            if self.program_id:
                transactions = transactions.filter(
                    sql_product__program_id=self.program_id
                )

            stock_results = transactions.exclude(
                report__date__gt=self.datetime
            ).order_by(
                'product_id', '-report__date'
            ).values_list(
                'product_id', 'stock_on_hand'
            ).distinct(
                'product_id'
            )

            # take a pass over the data to format the stock on hand
            # values properly
            stock_results = [(p, format_decimal(soh)) for p, soh in stock_results]

            yield (loc.name, stock_results)


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

    def _include_advanced_data(self):
        # if this flag is not specified, we default to giving
        # all the data back
        return self.config.get('advanced_columns', True)

    @property
    @memoized
    def _slug_attrib_map(self):
        @memoized
        def product_name(product_id):
            return Product.get(product_id).name
        @memoized
        def supply_point_location(case_id):
            return SupplyPointCase.get(case_id).location_id

        raw_map = {
            self.SLUG_PRODUCT_NAME: lambda s: product_name(s.product_id),
            self.SLUG_PRODUCT_ID: 'product_id',
            self.SLUG_CURRENT_STOCK: 'stock_on_hand',
        }
        if self._include_advanced_data():
            raw_map.update({
                self.SLUG_LOCATION_ID: lambda s: supply_point_location(s.case_id),
                self.SLUG_CONSUMPTION: lambda s: s.get_monthly_consumption(),
                self.SLUG_MONTHS_REMAINING: 'months_remaining',
                self.SLUG_CATEGORY: 'stock_category',
                # SLUG_STOCKOUT_SINCE: 'stocked_out_since',
                # SLUG_STOCKOUT_DURATION: 'stockout_duration_in_months',
                self.SLUG_LAST_REPORTED: 'last_modified_date',
                self.SLUG_RESUPPLY_QUANTITY_NEEDED: 'resupply_quantity_needed',
            })

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

        stock_states = StockState.objects.filter(
            section_id=STOCK_SECTION_TYPE,
            last_modified_date__lte=self.end_date,
            last_modified_date__gte=self.start_date,
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

    def leaf_node_data(self, stock_states):
        for state in stock_states:
            product = Product.get(state.product_id)

            result = {
                'product_id': product._id,
                'product_name': product.name,
                'current_stock': format_decimal(state.stock_on_hand),
            }

            if self._include_advanced_data():
                result.update({
                    'location_id': SupplyPointCase.get(state.case_id).location_id,
                    'location_lineage': None,
                    'category': state.stock_category,
                    'consumption': state.get_monthly_consumption(),
                    'months_remaining': state.months_remaining,
                    'resupply_quantity_needed': state.resupply_quantity_needed
                })

            yield result

    def aggregated_data(self, stock_states):
        def _convert_to_daily(consumption):
            return consumption / 30 if consumption is not None else None

        if self._include_advanced_data():
            product_aggregation = {}
            for state in stock_states:
                if state.product_id in product_aggregation:
                    product = product_aggregation[state.product_id]
                    product['current_stock'] = format_decimal(
                        product['current_stock'] + state.stock_on_hand
                    )

                    consumption = state.get_monthly_consumption()
                    if product['consumption'] is None:
                        product['consumption'] = consumption
                    elif consumption is not None:
                        product['consumption'] += consumption

                    product['count'] += 1

                    if state.sql_location is not None:
                        location_type = state.sql_location.location_type
                        product['category'] = stock_category(
                            product['current_stock'],
                            _convert_to_daily(product['consumption']),
                            location_type.understock_threshold,
                            location_type.overstock_threshold,
                        )
                    else:
                        product['category'] = 'nodata'

                    product['months_remaining'] = months_of_stock_remaining(
                        product['current_stock'],
                        _convert_to_daily(product['consumption'])
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
                        'current_stock': format_decimal(state.stock_on_hand),
                        'count': 1,
                        'consumption': consumption,
                        'category': state_stock_category(state),
                        'months_remaining': months_of_stock_remaining(
                            state.stock_on_hand,
                            _convert_to_daily(consumption)
                        )
                    }

            return product_aggregation.values()
        else:
            # If we don't need advanced data, we can
            # just do some orm magic.
            #
            # Note: this leaves out some harder to get quickly
            # values like location_id, but shouldn't be needed
            # unless we expand what uses this.
            aggregated_states = stock_states.values_list(
                'sql_product__name',
                'sql_product__product_id',
            ).annotate(stock_on_hand=Sum('stock_on_hand'))
            result = []
            for ag in aggregated_states:
                result.append({
                    'product_name': ag[0],
                    'product_id': ag[1],
                    'current_stock': format_decimal(ag[2])
                })

            return result

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
        locs = _location_map(by_supply_point.keys())

        for loc_id, subcases in by_supply_point.iteritems():
            if loc_id not in locs:
                continue  # it's archived, skip
            loc = locs[loc_id]
            by_product = dict((c['product_id'], c) for c in subcases)

            rec = {
                'name': loc.name,
                'type': loc.location_type.name,
                'geo': geopoint(loc),
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

    @property
    def converted_start_datetime(self):
        start_date = self.start_date
        if isinstance(start_date, unicode):
            start_date = parser.parse(start_date)
        return start_date

    @property
    def converted_end_datetime(self):
        end_date = self.end_date
        if isinstance(end_date, unicode):
            end_date = parser.parse(end_date)
        return end_date

    def get_data(self):
        # todo: this will probably have to paginate eventually
        if self.all_relevant_forms:
            sp_ids = get_relevant_supply_point_ids(
                self.domain,
                self.active_location,
            )

            form_xmlnses = [form['xmlns'] for form in self.all_relevant_forms.values()]
            spoint_loc_map = {
                doc['_id']: doc['location_id']
                for doc in iter_docs(SupplyPointCase.get_db(), sp_ids)
            }
            locations = _location_map(spoint_loc_map.values())

            for spoint_id, loc_id in spoint_loc_map.items():
                if loc_id not in locations:
                    continue  # it's archived, skip
                loc = locations[loc_id]

                results = StockReport.objects.filter(
                    stocktransaction__case_id=spoint_id
                ).filter(
                    date__gte=self.converted_start_datetime,
                    date__lte=self.converted_end_datetime
                ).values_list(
                    'form_id',
                    'date'
                ).distinct()  # not truly distinct due to ordering

                matched = False
                for form_id, date in results:
                    try:
                        if XFormInstance.get(form_id).xmlns in form_xmlnses:
                            yield {
                                'parent_name': loc.parent.name if loc.parent else '',
                                'loc_id': loc.location_id,
                                'loc_path': loc.path,
                                'name': loc.name,
                                'type': loc.location_type.name,
                                'reporting_status': 'reporting',
                                'geo': geopoint(loc),
                                'last_reporting_date': date,
                            }
                            matched = True
                            break
                    except ResourceNotFound:
                        logging.error('Stock report for location {} in {} references non-existent form {}'.format(
                            loc.location_id, loc.domain, form_id
                        ))

                if not matched:
                    result = StockReport.objects.filter(
                        stocktransaction__case_id=spoint_id
                    ).values_list(
                        'date'
                    ).order_by('-date')[:1]
                    yield {
                        'parent_name': loc.parent.name if loc.parent else '',
                        'loc_id': loc.location_id,
                        'loc_path': loc.path,
                        'name': loc.name,
                        'type': loc.location_type.name,
                        'reporting_status': 'nonreporting',
                        'geo': geopoint(loc),
                        'last_reporting_date': result[0][0] if result else ''
                    }
