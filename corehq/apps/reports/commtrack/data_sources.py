from datetime import datetime, timedelta
from decimal import Decimal

from dateutil import parser
from memoized import memoized

from casexml.apps.stock.const import SECTION_TYPE_STOCK
from casexml.apps.stock.utils import months_of_stock_remaining, stock_category
from dimagi.utils.couch.loosechange import map_reduce

from corehq.apps.locations.models import SQLLocation
from corehq.apps.products.models import Product
from corehq.apps.reports.analytics.dbaccessors import (
    get_aggregated_ledger_values,
    get_wrapped_ledger_values,
)
from corehq.apps.reports.api import ReportDataSource
from corehq.apps.reports.commtrack.const import STOCK_SECTION_TYPE
from corehq.apps.reports.commtrack.util import (
    get_consumption_helper_from_ledger_value,
    get_product_id_name_mapping,
    get_product_ids_for_program,
    get_relevant_supply_point_ids,
)


def format_decimal(d):
    """Remove exponent and trailing zeros.

        >>> format_decimal(Decimal('5E+3'))
        Decimal('5000')

        https://docs.python.org/2/library/decimal.html#decimal-faq
    """
    if d is not None:
        return d.quantize(Decimal(1)) if d == d.to_integral() else d.normalize()


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
        loc_id = self.config.get('location_id')
        return SQLLocation.objects.get_or_None(domain=self.domain, location_id=loc_id)

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
    @memoized
    def product_ids(self):
        if self.program_id:
            return get_product_ids_for_program(self.domain, self.program_id)

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

    @property
    def datetime(self):
        """
        Returns a datetime object at the end of the selected
        (or current) date. This is needed to properly filter
        transactions that occur during the day we are filtering
        for
        """
        # note: empty string is parsed as today's date
        date = self.config.get('date') or ''

        try:
            date = parser.parse(date).date()
        except ValueError:
            date = datetime.utcnow().date()

        return datetime(date.year, date.month, date.day, 23, 59, 59)

    def get_data(self):
        from corehq.form_processor.backends.sql.dbaccessors import LedgerAccessorSQL
        locations = self.locations()

        # locations at this point will only have location objects
        # that have supply points associated
        for loc in locations[:self.config.get('max_rows', 100)]:
            # TODO: this is very inefficient since it loads ALL the transactions up to the supplied
            # date but only requires the most recent one. Should rather use a window function.
            transactions = LedgerAccessorSQL.get_ledger_transactions_in_window(
                case_id=loc.supply_point_id,
                section_id=SECTION_TYPE_STOCK,
                entry_id=None,
                window_start=datetime.min,
                window_end=self.datetime,
            )

            if self.program_id:
                transactions = (
                    tx for tx in transactions
                    if tx.entry_id in self.product_ids
                )

            stock_results = sorted(transactions, key=lambda tx: tx.report_date, reverse=False)
            yield (loc.name, {tx.entry_id: tx.updated_balance for tx in stock_results})

    def locations(self):
        if self.active_location:
            if self.active_location.supply_point_id:
                locations = [self.active_location]
            else:
                locations = []

            locations += list(
                self.active_location.get_descendants().filter(
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

        return locations


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
        current_stock: The current stock level
        consumption: The current monthly consumption rate
        months_remaining: The number of months remaining until stock out
        category: The status category. See casexml.apps.stock.utils.stock_category
        resupply_quantity_needed: Max amount - current amount

    """
    slug = 'agg_stock_status'

    SLUG_PRODUCT_NAME = 'product_name'
    SLUG_PRODUCT_ID = 'product_id'
    SLUG_MONTHS_REMAINING = 'months_remaining'
    SLUG_CONSUMPTION = 'consumption'
    SLUG_CURRENT_STOCK = 'current_stock'
    SLUG_LOCATION_ID = 'location_id'
    SLUG_STOCKOUT_SINCE = 'stockout_since'
    SLUG_STOCKOUT_DURATION = 'stockout_duration'
    SLUG_LAST_REPORTED = 'last_reported'
    SLUG_CATEGORY = 'category'
    SLUG_RESUPPLY_QUANTITY_NEEDED = 'resupply_quantity_needed'

    def _include_advanced_data(self):
        # if this flag is not specified, we default to giving
        # all the data back
        return self.config.get('advanced_columns', True)

    def slugs(self):
        slugs = [
            self.SLUG_PRODUCT_NAME,
            self.SLUG_PRODUCT_ID,
            self.SLUG_CURRENT_STOCK,
        ]
        if self._include_advanced_data():
            slugs.extend([
                self.SLUG_LOCATION_ID,
                self.SLUG_CONSUMPTION,
                self.SLUG_MONTHS_REMAINING,
                self.SLUG_CATEGORY,
                self.SLUG_LAST_REPORTED,
                self.SLUG_RESUPPLY_QUANTITY_NEEDED,
            ])
        return slugs

    def get_data(self):
        sp_ids = get_relevant_supply_point_ids(self.domain, self.active_location)
        if len(sp_ids) == 1:
            return self.leaf_node_data(sp_ids[0])
        else:
            if self.config.get('aggregate'):
                return self.aggregated_data(sp_ids)
            else:
                return self.raw_product_states(sp_ids)

    def leaf_node_data(self, supply_point_id):
        ledger_values = get_wrapped_ledger_values(
            self.domain,
            [supply_point_id],
            section_id=STOCK_SECTION_TYPE,
            entry_ids=self.product_ids
        )
        for ledger_value in ledger_values:
            result = {
                'product_id': ledger_value.sql_product.product_id,
                'product_name': ledger_value.sql_product.name,
                'current_stock': format_decimal(Decimal(ledger_value.balance)),
            }

            if self._include_advanced_data():
                consumption_helper = get_consumption_helper_from_ledger_value(self.domain, ledger_value)
                result.update({
                    'location_id': ledger_value.location_id,
                    'category': consumption_helper.get_stock_category(),
                    'consumption': consumption_helper.get_monthly_consumption(),
                    'months_remaining': consumption_helper.get_months_remaining(),
                    'resupply_quantity_needed': consumption_helper.get_resupply_quantity_needed()
                })

            yield result

    def aggregated_data(self, supply_point_ids):

        def _convert_to_daily(consumption):
            return consumption / 30 if consumption is not None else None

        if self._include_advanced_data():
            product_aggregation = {}
            ledger_values = get_wrapped_ledger_values(
                domain=self.domain,
                case_ids=supply_point_ids,
                section_id=STOCK_SECTION_TYPE,
                entry_ids=self.product_ids
            )
            for ledger_value in ledger_values:
                consumption_helper = get_consumption_helper_from_ledger_value(self.domain, ledger_value)
                if ledger_value.entry_id in product_aggregation:
                    product = product_aggregation[ledger_value.entry_id]
                    product['current_stock'] = format_decimal(
                        product['current_stock'] + ledger_value.balance
                    )

                    consumption = consumption_helper.get_monthly_consumption()
                    if product['consumption'] is None:
                        product['consumption'] = consumption
                    elif consumption is not None:
                        product['consumption'] += consumption

                    product['count'] += 1

                    if ledger_value.sql_location is not None:
                        location_type = ledger_value.sql_location.location_type
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
                    product = ledger_value.sql_product
                    consumption = consumption_helper.get_monthly_consumption()

                    product_aggregation[ledger_value.entry_id] = {
                        'product_id': ledger_value.entry_id,
                        'location_id': None,
                        'product_name': product.name,
                        'resupply_quantity_needed': None,
                        'current_stock': format_decimal(Decimal(ledger_value.balance)),
                        'count': 1,
                        'consumption': consumption,
                        'category': consumption_helper.get_stock_category(),
                        'months_remaining': months_of_stock_remaining(
                            ledger_value.balance,
                            _convert_to_daily(consumption)
                        )
                    }

            return list(product_aggregation.values())
        else:
            # If we don't need advanced data, we can
            # just do some orm magic.
            #
            # Note: this leaves out some harder to get quickly
            # values like location_id, but shouldn't be needed
            # unless we expand what uses this.
            aggregated_ledger_values = get_aggregated_ledger_values(
                domain=self.domain,
                case_ids=supply_point_ids,
                section_id=STOCK_SECTION_TYPE,
                entry_ids=self.product_ids
            )

            product_name_map = get_product_id_name_mapping(self.domain)
            result = []
            for ag in aggregated_ledger_values:
                result.append({
                    'product_name': product_name_map.get(ag.entry_id),
                    'product_id': ag.entry_id,
                    'current_stock': format_decimal(Decimal(ag.balance))
                })

            return result

    def raw_product_states(self, supply_point_ids):
        ledger_values = get_wrapped_ledger_values(
            domain=self.domain,
            case_ids=supply_point_ids,
            section_id=STOCK_SECTION_TYPE,
            entry_ids=self.product_ids
        )
        for ledger_value in ledger_values:
            yield self._get_dict_for_ledger_value(ledger_value)

    def _get_dict_for_ledger_value(self, ledger_value):
        values = {
            self.SLUG_PRODUCT_NAME: ledger_value.sql_product.name,
            self.SLUG_PRODUCT_ID: ledger_value.entry_id,
            self.SLUG_CURRENT_STOCK: ledger_value.balance,
        }

        if self._include_advanced_data():
            consumption_helper = get_consumption_helper_from_ledger_value(self.domain, ledger_value)
            values.update({
                self.SLUG_LOCATION_ID: ledger_value.location_id,
                self.SLUG_CONSUMPTION: consumption_helper.get_monthly_consumption(),
                self.SLUG_MONTHS_REMAINING: consumption_helper.get_months_remaining(),
                self.SLUG_CATEGORY: consumption_helper.get_stock_category(),
                self.SLUG_LAST_REPORTED: ledger_value.last_modified,
                self.SLUG_RESUPPLY_QUANTITY_NEEDED: consumption_helper.get_resupply_quantity_needed()
            })

        return values


class StockStatusBySupplyPointDataSource(StockStatusDataSource):

    def get_data(self):
        data = list(super(StockStatusBySupplyPointDataSource, self).get_data())

        products = dict((r['product_id'], r['product_name']) for r in data)
        product_ids = sorted(products, key=lambda e: products[e])

        by_supply_point = map_reduce(lambda e: [(e['location_id'],)], data=data, include_docs=True)
        locs = _location_map(list(by_supply_point))

        for loc_id, subcases in by_supply_point.items():
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
