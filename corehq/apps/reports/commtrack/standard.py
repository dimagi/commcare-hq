from __future__ import absolute_import
from __future__ import division
from corehq.apps.domain.models import Domain
from corehq.apps.reports.analytics.esaccessors import get_wrapped_ledger_values
from corehq.apps.reports.commtrack.data_sources import (
    StockStatusDataSource, ReportingStatusDataSource,
    SimplifiedInventoryDataSource, SimplifiedInventoryDataSourceNew
)
from corehq.apps.reports.generic import GenericTabularReport
from corehq.apps.reports.datatables import DataTablesHeader, DataTablesColumn
from corehq.apps.commtrack.models import CommtrackConfig, CommtrackActionConfig
from corehq.apps.products.models import Product, SQLProduct
from corehq.apps.reports.graph_models import PieChart, MultiBarChart, Axis
from corehq.apps.reports.standard import ProjectReport, ProjectReportParametersMixin, DatespanMixin
from corehq.apps.reports.filters.commtrack import SelectReportingType
from corehq.form_processor.utils.general import should_use_sql_backend
from dimagi.utils.couch.loosechange import map_reduce
from corehq.apps.locations.models import SQLLocation
from dimagi.utils.decorators.memoized import memoized
from django.utils.translation import ugettext as _, ugettext_noop
from corehq.apps.reports.commtrack.util import get_relevant_supply_point_ids, get_product_id_name_mapping, \
    get_product_ids_for_program, get_consumption_helper_from_ledger_value
from corehq.apps.reports.commtrack.const import STOCK_SECTION_TYPE
from corehq.apps.reports.filters.commtrack import AdvancedColumns
import six


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

    def ordered_products(self, ordering):
        return sorted(self.products, key=lambda p: (0, ordering.index(p['name'])) if p['name'] in ordering else (1, p['name']))

    @property
    def actions(self):
        return sorted(action_config.name for action_config in self.config.actions)

    def ordered_actions(self, ordering):
        return sorted(self.actions, key=lambda a: (0, ordering.index(a)) if a in ordering else (1, a))

    @property
    def incr_actions(self):
        """action types that increment/decrement stock"""
        actions = [action_config for action_config in self.config.actions if action_config.action_type in ('receipts', 'consumption')]
        if not any(a.action_type == 'consumption' for a in actions):
            # add implicitly calculated consumption -- TODO find a way to refer to this more explicitly once we track different kinds of consumption (losses, etc.)
            actions.append(CommtrackActionConfig(action_type='consumption', caption='Consumption'))
        return actions

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

    @property
    @memoized
    def aggregate_by(self):
        return self.request.GET.get('agg_type')


class CurrentStockStatusReport(GenericTabularReport, CommtrackReportMixin):
    name = ugettext_noop('Stock Status by Product')
    slug = 'current_stock_status'
    fields = [
        'corehq.apps.reports.filters.fixtures.AsyncLocationFilter',
        'corehq.apps.reports.filters.commtrack.ProgramFilter',
    ]
    exportable = True
    emailable = True

    @classmethod
    def display_in_dropdown(cls, domain=None, project=None, user=None):
        return True

    @property
    def headers(self):
        columns = [
            DataTablesColumn(_('Product')),
            DataTablesColumn(_('# Facilities')),
            DataTablesColumn(
                _('Stocked Out'),
                help_text=_("A facility is counted as stocked out when its \
                            current stock is below the emergency level.")),
            DataTablesColumn(
                _('Understocked'),
                help_text=_("A facility is counted as under stocked when its \
                            current stock is above the emergency level but below the \
                            low stock level.")),
            DataTablesColumn(
                _('Adequate Stock'),
                help_text=_("A facility is counted as adequately stocked when \
                            its current stock is above the low level but below the \
                            overstock level.")),
            DataTablesColumn(
                _('Overstocked'),
                help_text=_("A facility is counted as overstocked when \
                            its current stock is above the overstock level.")),
            DataTablesColumn(
                _('Insufficient Data'),
                help_text=_("A facility is marked as insufficient data when \
                            there is no known consumption amount or there \
                            has never been a stock report at the location. \
                            Consumption amount can be unknown if there is \
                            either no default consumption value or the reporting \
                            history does not meet the calculation settings \
                            for the project."))
        ]
        return DataTablesHeader(*columns)

    @property
    @memoized
    def product_data(self):
        return list(self.get_prod_data())

    def get_prod_data(self):
        sp_ids = get_relevant_supply_point_ids(self.domain, self.active_location)
        product_ids = get_product_ids_for_program(self.domain, self.program_id) if self.program_id else None

        ledger_values = get_wrapped_ledger_values(
            domain=self.domain,
            case_ids=sp_ids,
            section_id=STOCK_SECTION_TYPE,
            entry_ids=product_ids,
        )
        product_grouping = {}
        for ledger_value in ledger_values:
            consumption_helper = get_consumption_helper_from_ledger_value(
                Domain.get_by_name(self.domain), ledger_value
            )
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

        product_name_map = get_product_id_name_mapping(self.domain)
        rows = [[
            product_name_map.get(product['entry_id'], product['entry_id']),
            product['facility_count'],
            100.0 * product['stockout'] / product['facility_count'],
            100.0 * product['understock'] / product['facility_count'],
            100.0 * product['adequate'] / product['facility_count'],
            100.0 * product['overstock'] / product['facility_count'],
            100.0 * product['nodata'] / product['facility_count'],
        ] for product in product_grouping.values()]

        return sorted(rows, key=lambda r: r[0].lower())

    @property
    def rows(self):
        return [pd[0:2] + ['%.1f%%' % d for d in pd[2:]] for pd in self.product_data]

    def get_data_for_graph(self):
        ret = [
            {"key": "stocked out", "color": "#e00707"},
            {"key": "under stock", "color": "#ffb100"},
            {"key": "adequate stock", "color": "#4ac925"},
            {"key": "overstocked", "color": "#b536da"},
            {"key": "unknown", "color": "#ABABAB"}
        ]
        statuses = ['stocked out', 'under stock', 'adequate stock', 'overstocked', 'no data']

        for r in ret:
            r["values"] = []

        for pd in self.product_data:
            for i, status in enumerate(statuses):
                ret[i]['values'].append({"x": pd[0], "y": pd[i+2]})

        return ret

    @property
    def charts(self):
        # only get data if we're loading an actual report - this requires filters
        if 'location_id' in self.request.GET:
            chart = MultiBarChart(None, Axis(_('Products')), Axis(_('% of Facilities'), ',.1d'))
            chart.data = self.get_data_for_graph()
            return [chart]


class SimplifiedInventoryReport(GenericTabularReport, CommtrackReportMixin):
    name = ugettext_noop('Inventory by Location')
    slug = SimplifiedInventoryDataSource.slug
    special_notice = ugettext_noop('A maximum of 100 locations will be shown. Filter by location if you need to see more.')
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

        if should_use_sql_backend(self.domain):
            data = SimplifiedInventoryDataSourceNew(config).get_data()
        else:
            data = SimplifiedInventoryDataSource(config).get_data()

        for loc_name, loc_data in data:
            yield [loc_name] + [
                loc_data.get(p.product_id, _('No data'))
                for p in self.products
            ]


class InventoryReport(GenericTabularReport, CommtrackReportMixin):
    name = ugettext_noop('Aggregate Inventory')
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
        def fmt(val, formatter=lambda k: k, default=u'\u2014'):
            return formatter(val) if val is not None else default

        statuses = {
            'nodata': _('no data'),
            'stockout': _('stock-out'),
            'understock': _('under-stock'),
            'adequate': _('adequate'),
            'overstock': _('over-stock'),
        }

        for row in sorted(self.product_data,  key=lambda p: p[StockStatusDataSource.SLUG_PRODUCT_NAME]):
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


class ReportingRatesReport(GenericTabularReport, CommtrackReportMixin):
    name = ugettext_noop('Reporting Rate')
    slug = 'reporting_rate'
    fields = [
        'corehq.apps.reports.filters.fixtures.AsyncLocationFilter',
        'corehq.apps.reports.filters.forms.FormsByApplicationFilter',
        'corehq.apps.reports.filters.dates.DatespanFilter',
        'corehq.apps.reports.filters.commtrack.SelectReportingType',
    ]
    exportable = True
    emailable = True

    @classmethod
    def display_in_dropdown(cls, domain=None, project=None, user=None):
        return True

    def is_aggregate_report(self):
        return self.request.GET.get(SelectReportingType.slug, '') != 'facilities'

    @property
    def headers(self):
        if self.is_aggregate_report():
            return DataTablesHeader(*(DataTablesColumn(text) for text in [
                _('Location'),
                _('# Sites'),
                _('# Reporting'),
                _('Reporting Rate'),
                _('# Non-reporting'),
                _('Non-reporting Rate'),
            ]))
        else:
            return DataTablesHeader(*(DataTablesColumn(text) for text in [
                _('Location'),
                _('Parent location'),
                _('Date of last report for selected period'),
                _('Reporting'),
            ]))

    @property
    @memoized
    def _facility_data(self):
        config = {
            'domain': self.domain,
            'location_id': self.request.GET.get('location_id'),
            'startdate': self.datespan.startdate_utc,
            'enddate': self.datespan.enddate_utc,
            'request': self.request,
        }
        statuses = list(ReportingStatusDataSource(config).get_data())

        results = []
        for status in statuses:
            results.append([
                status['name'],
                status['parent_name'],
                status['last_reporting_date'].date() if status['last_reporting_date'] else _('Never'),
                _('Yes') if status['reporting_status'] == 'reporting' else _('No'),
            ])

        master_tally = self.status_tally([site['reporting_status'] for site in statuses])

        return master_tally, results

    @property
    @memoized
    def _aggregate_data(self):
        config = {
            'domain': self.domain,
            'location_id': self.request.GET.get('location_id'),
            'startdate': self.datespan.startdate_utc,
            'enddate': self.datespan.enddate_utc,
            'request': self.request,
        }
        statuses = list(ReportingStatusDataSource(config).get_data())

        def child_loc(path):
            root = self.active_location
            ix = path.index(root.location_id) if root else -1
            try:
                return path[ix + 1]
            except IndexError:
                return None

        def case_iter():
            for site in statuses:
                if child_loc(site['loc_path']) is not None:
                    yield (site['loc_path'], site['reporting_status'])
        status_by_agg_site = map_reduce(lambda path_status: [(child_loc(path_status[0]), path_status[1])],
                                        data=case_iter())
        sites_by_agg_site = map_reduce(lambda path_status1: [(child_loc(path_status1[0]), path_status1[0][-1])],
                                       data=case_iter())

        status_counts = dict((loc_id, self.status_tally(statuses))
                             for loc_id, statuses in six.iteritems(status_by_agg_site))

        master_tally = self.status_tally([site['reporting_status'] for site in statuses])

        locs = (SQLLocation.objects
                .filter(is_archived=False,
                        location_id__in=list(status_counts))
                .order_by('name'))

        def fmt(pct):
            return '%.1f%%' % (100. * pct)

        def fmt_pct_col(loc_id, col_type):
            return fmt(status_counts[loc_id].get(col_type, {'pct': 0.})['pct'])

        def fmt_count_col(loc_id, col_type):
            return status_counts[loc_id].get(col_type, {'count': 0})['count']

        def _rows():
            for loc in locs:
                row = [loc.name, len(sites_by_agg_site[loc.location_id])]
                for k in ('reporting', 'nonreporting'):
                    row.append(fmt_count_col(loc.location_id, k))
                    row.append(fmt_pct_col(loc.location_id, k))

                yield row

        return master_tally, _rows()

    def status_tally(self, statuses):
        total = len(statuses)

        return map_reduce(lambda s: [(s,)],
                          lambda v: {'count': len(v), 'pct': len(v) / float(total)},
                          data=statuses)

    @property
    def rows(self):
        if self.is_aggregate_report():
            return self._aggregate_data[1]
        else:
            return self._facility_data[1]

    def master_pie_chart_data(self):
        if self.is_aggregate_report():
            tally = self._aggregate_data[0]
        else:
            tally = self._facility_data[0]

        labels = {
            'reporting': _('Reporting'),
            'nonreporting': _('Non-reporting'),
        }
        return [{'label': labels[k], 'value': tally.get(k, {'count': 0.})['count']} for k in ('reporting', 'nonreporting')]

    @property
    def charts(self):
        if 'location_id' in self.request.GET: # hack: only get data if we're loading an actual report
            chart = PieChart(_('Current Reporting'), 'current_reporting', [])
            chart.data = self.master_pie_chart_data()
            return [chart]
