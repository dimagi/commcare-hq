from django.utils.functional import cached_property
from django.utils.translation import gettext as _
from django.utils.translation import gettext_noop

from memoized import memoized

from corehq.apps.commtrack.models import CommtrackConfig
from corehq.apps.locations.models import SQLLocation
from corehq.apps.products.models import Product, SQLProduct
from corehq.apps.reports.analytics.dbaccessors import (
    get_wrapped_ledger_values,
    products_with_ledgers,
)
from corehq.apps.reports.commtrack.const import STOCK_SECTION_TYPE
from corehq.apps.reports.commtrack.data_sources import (
    SimplifiedInventoryDataSource,
    StockStatusDataSource,
)
from corehq.apps.reports.commtrack.util import (
    get_consumption_helper_from_ledger_value,
    get_product_id_name_mapping,
    get_product_ids_for_program,
    get_relevant_supply_point_ids,
)
from corehq.apps.reports.datatables import DataTablesColumn, DataTablesHeader
from corehq.apps.reports.filters.commtrack import AdvancedColumns
from corehq.apps.reports.generic import GenericTabularReport
from corehq.apps.reports.standard import (
    DatespanMixin,
    ProjectReport,
    ProjectReportParametersMixin,
)


class CommtrackReportMixin(ProjectReport, ProjectReportParametersMixin, DatespanMixin):

    @classmethod
    def show_in_navigation(cls, domain=None, project=None, user=None):
        return project and project.commtrack_enabled

    @property
    @memoized
    def config(self):
        return CommtrackConfig.for_domain(self.domain)

    @property
    @memoized
    def products(self):
        prods = Product.by_domain(self.domain, wrap=False)
        return sorted(prods, key=lambda p: p['name'])

    @property
    def actions(self):
        return sorted(action_config.name for action_config in self.config.actions)

    def ordered_actions(self, ordering):
        return sorted(self.actions, key=lambda a: (0, ordering.index(a)) if a in ordering else (1, a))

    @property
    @memoized
    def active_location(self):
        loc_id = self.request_params.get('location_id')
        return SQLLocation.objects.get_or_None(domain=self.domain, location_id=loc_id)

    @property
    @memoized
    def program_id(self):
        prog_id = self.request_params.get('program')
        if prog_id != '':
            return prog_id


class CurrentStockStatusReport(GenericTabularReport, CommtrackReportMixin):
    name = gettext_noop('Stock Status by Product')
    slug = 'current_stock_status'
    fields = [
        'corehq.apps.reports.filters.fixtures.AsyncLocationFilter',
        'corehq.apps.reports.filters.commtrack.ProgramFilter',
    ]
    exportable = True
    exportable_all = True
    emailable = True
    asynchronous = True
    ajax_pagination = True

    @property
    def shared_pagination_GET_params(self):
        return [
            {'name': 'location_id', 'value': self.request.GET.get('location_id')},
            {'name': 'program', 'value': self.request.GET.get('program')},
        ]

    @cached_property
    def _sp_ids(self):
        return get_relevant_supply_point_ids(self.domain, self.active_location)

    @cached_property
    def _program_product_ids(self):
        if self.program_id:
            return get_product_ids_for_program(self.domain, self.program_id)

    @cached_property
    def _product_name_mapping(self):
        return get_product_id_name_mapping(self.domain, self.program_id)

    @cached_property
    def _products_with_ledgers(self):
        return products_with_ledgers(self.domain, self._sp_ids, STOCK_SECTION_TYPE, self._program_product_ids)

    @cached_property
    def _desc_product_order(self):
        return self.request.GET.get('sSortDir_0') == 'desc'

    @property
    def total_records(self):
        return len(self._products_with_ledgers)

    @classmethod
    def display_in_dropdown(cls, domain=None, project=None, user=None):
        return True

    @property
    def headers(self):
        columns = [
            DataTablesColumn(_('Product')),
            DataTablesColumn(_('# Facilities'), sortable=False),
            DataTablesColumn(
                _('Stocked Out'),
                help_text=_("A facility is counted as stocked out when its \
                            current stock is below the emergency level."),
                sortable=False),
            DataTablesColumn(
                _('Understocked'),
                help_text=_("A facility is counted as under stocked when its \
                            current stock is above the emergency level but below the \
                            low stock level."),
                sortable=False),
            DataTablesColumn(
                _('Adequate Stock'),
                help_text=_("A facility is counted as adequately stocked when \
                            its current stock is above the low level but below the \
                            overstock level."),
                sortable=False),
            DataTablesColumn(
                _('Overstocked'),
                help_text=_("A facility is counted as overstocked when \
                            its current stock is above the overstock level."),
                sortable=False),
            DataTablesColumn(
                _('Insufficient Data'),
                help_text=_("A facility is marked as insufficient data when \
                            there is no known consumption amount or there \
                            has never been a stock report at the location. \
                            Consumption amount can be unknown if there is \
                            either no default consumption value or the reporting \
                            history does not meet the calculation settings \
                            for the project."),
                sortable=False)
        ]
        return DataTablesHeader(*columns)

    @cached_property
    def product_data(self):
        return list(self.get_prod_data())

    def filter_by_product_ids(self):
        """
        This sorts by name of products that should be shown according to filter and
        then returns the product ids to be shown according to the pagination
        """
        product_name_map = self._product_name_mapping
        # sort
        sorted_product_name_map = sorted(product_name_map.items(),
                                         key=lambda name_map: name_map[1],
                                         reverse=self._desc_product_order)
        # product to filter
        # -> that have ledgers and
        # -> fall into requested pagination
        return [product_id for product_id, product_name in sorted_product_name_map
                if product_id in self._products_with_ledgers
                ][self.pagination.start:][:self.pagination.count]

    def get_prod_data(self):
        ledger_values = get_wrapped_ledger_values(
            domain=self.domain,
            case_ids=self._sp_ids,
            section_id=STOCK_SECTION_TYPE,
            entry_ids=self.filter_by_product_ids(),
        )
        product_grouping = {}
        for ledger_value in ledger_values:
            consumption_helper = get_consumption_helper_from_ledger_value(self.domain, ledger_value)
            status = consumption_helper.get_stock_category()
            if ledger_value.entry_id in product_grouping:
                product_grouping[ledger_value.entry_id][status] += 1
                product_grouping[ledger_value.entry_id]['facility_count'] += 1

            else:
                product_grouping[ledger_value.entry_id] = {
                    'entry_id': ledger_value.entry_id,
                    'stockout': 0,
                    'understock': 0,
                    'overstock': 0,
                    'adequate': 0,
                    'nodata': 0,
                    'facility_count': 1
                }
                product_grouping[ledger_value.entry_id][status] = 1
        product_name_map = self._product_name_mapping
        rows = [[
            product_name_map.get(product['entry_id'], product['entry_id']),
            product['facility_count'],
            100.0 * product['stockout'] / product['facility_count'],
            100.0 * product['understock'] / product['facility_count'],
            100.0 * product['adequate'] / product['facility_count'],
            100.0 * product['overstock'] / product['facility_count'],
            100.0 * product['nodata'] / product['facility_count'],
        ] for product in product_grouping.values()]

        return sorted(rows, key=lambda r: r[0].lower(),
                      reverse=self._desc_product_order)

    @property
    def rows(self):
        return [pd[0:2] + ['%.1f%%' % d for d in pd[2:]] for pd in self.product_data]

    @property
    def get_all_rows(self):
        self.pagination.count = self.total_records
        return self.rows


class SimplifiedInventoryReport(GenericTabularReport, CommtrackReportMixin):
    name = gettext_noop('Inventory by Location')
    slug = SimplifiedInventoryDataSource.slug
    special_notice = gettext_noop('A maximum of 100 locations will be shown. '
                                  'Filter by location if you need to see more.')
    exportable = True
    emailable = True
    fields = [
        'corehq.apps.reports.filters.fixtures.AsyncLocationFilter',
        'corehq.apps.reports.filters.commtrack.ProgramFilter',
        'corehq.apps.reports.filters.dates.SingleDateFilter',
    ]

    @property
    @memoized
    def products(self):
        products = SQLProduct.active_objects.filter(domain=self.domain)
        if self.program_id:
            products = products.filter(program_id=self.program_id)
        return list(products.order_by('name'))

    @property
    def headers(self):
        columns = [
            DataTablesColumn(_('Location')),
        ]

        columns += [DataTablesColumn(p.name) for p in self.products]

        return DataTablesHeader(*columns)

    @property
    def rows(self):
        config = {
            'domain': self.domain,
            'location_id': self.request.GET.get('location_id'),
            'program_id': self.program_id,
            'date': self.request.GET.get('date', None),
            'max_rows': 100
        }

        data = SimplifiedInventoryDataSource(config).get_data()

        for loc_name, loc_data in data:
            yield [loc_name] + [
                loc_data.get(p.product_id, _('No data'))
                for p in self.products
            ]


class InventoryReport(GenericTabularReport, CommtrackReportMixin):
    name = gettext_noop('Aggregate Inventory')
    slug = StockStatusDataSource.slug
    fields = [
        'corehq.apps.reports.filters.fixtures.AsyncLocationFilter',
        'corehq.apps.reports.filters.commtrack.ProgramFilter',
        'corehq.apps.reports.filters.commtrack.AdvancedColumns',
    ]
    exportable = True
    emailable = True

    @classmethod
    def display_in_dropdown(cls, domain=None, project=None, user=None):
        return True

    def showing_advanced_columns(self):
        return AdvancedColumns.get_value(self.request, self.domain)

    @property
    def headers(self):
        columns = [
            DataTablesColumn(_('Product')),
            DataTablesColumn(_('Stock on Hand'),
                help_text=_('Total stock on hand for all locations matching the filters.')),
        ]

        if self.showing_advanced_columns():
            columns += [
                DataTablesColumn(_('Monthly Consumption'),
                    help_text=_('Total average monthly consumption for all locations matching the filters.')),
                DataTablesColumn(_('Months of Stock'),
                    help_text=_('Number of months of stock remaining for all locations matching the filters. \
                                Computed by calculating stock on hand divided by monthly consumption.')),
                DataTablesColumn(_('Stock Status'),
                    help_text=_('Stock status prediction made using calculated consumption \
                                or project specific default values. "No Data" means that \
                                there is not enough data to compute consumption and default \
                                values have not been uploaded yet.')),
                # DataTablesColumn(_('Resupply Quantity Suggested')),
            ]

        return DataTablesHeader(*columns)

    @property
    @memoized
    def product_data(self):
        config = {
            'domain': self.domain,
            'location_id': self.request.GET.get('location_id'),
            'program_id': self.request.GET.get('program'),
            'aggregate': True,
            'advanced_columns': self.showing_advanced_columns(),
        }
        return list(StockStatusDataSource(config).get_data())

    @property
    def rows(self):
        def fmt(val, formatter=lambda k: k, default='\u2014'):
            return formatter(val) if val is not None else default

        statuses = {
            'nodata': _('no data'),
            'stockout': _('stock-out'),
            'understock': _('under-stock'),
            'adequate': _('adequate'),
            'overstock': _('over-stock'),
        }

        for row in sorted(self.product_data, key=lambda p: p[StockStatusDataSource.SLUG_PRODUCT_NAME]):
            result = [
                fmt(row[StockStatusDataSource.SLUG_PRODUCT_NAME]),
                fmt(row[StockStatusDataSource.SLUG_CURRENT_STOCK]),
            ]
            if self.showing_advanced_columns():
                result += [
                    fmt(row[StockStatusDataSource.SLUG_CONSUMPTION], int),
                    fmt(row[StockStatusDataSource.SLUG_MONTHS_REMAINING], lambda k: '%.1f' % k),
                    fmt(row[StockStatusDataSource.SLUG_CATEGORY], lambda k: statuses.get(k, k)),
                ]
            yield result
