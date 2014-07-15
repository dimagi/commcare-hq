from corehq.apps.api.es import CaseES
from corehq.apps.commtrack.psi_hacks import is_psi_domain
from corehq.apps.reports.commtrack.data_sources import StockStatusDataSource, ReportingStatusDataSource
from corehq.apps.reports.generic import GenericTabularReport
from corehq.apps.reports.datatables import DataTablesHeader, DataTablesColumn
from corehq.apps.commtrack.models import Product, CommtrackConfig, CommtrackActionConfig, StockState
from corehq.apps.reports.graph_models import PieChart, MultiBarChart, Axis
from corehq.apps.reports.standard import ProjectReport, ProjectReportParametersMixin, DatespanMixin
from dimagi.utils.couch.loosechange import map_reduce
from datetime import datetime
from corehq.apps.locations.models import Location
from dimagi.utils.decorators.memoized import memoized
from django.utils.translation import ugettext as _, ugettext_noop
from corehq.apps.reports.standard.cases.basic import CaseListReport
from corehq.apps.reports.standard.cases.data_sources import CaseDisplay
from corehq.apps.reports.commtrack.util import get_relevant_supply_point_ids, product_ids_filtered_by_program
from corehq.apps.reports.commtrack.const import STOCK_SECTION_TYPE


def _enabled_hack(domain):
    return not is_psi_domain(domain)


class CommtrackReportMixin(ProjectReport, ProjectReportParametersMixin, DatespanMixin):

    @classmethod
    def show_in_navigation(cls, domain=None, project=None, user=None):
        return project.commtrack_enabled

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
        if is_psi_domain(self.domain):
            ordering = ['sales', 'receipts', 'consumption']
            actions.sort(key=lambda a: (0, ordering.index(a.action_name)) if a.action_name in ordering else (1, a.action_name))
        return actions

    @property
    @memoized
    def active_location(self):
        loc_id = self.request_params.get('location_id')
        if loc_id:
            return Location.get(loc_id)

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
    fields = ['corehq.apps.reports.filters.fixtures.AsyncLocationFilter',
              'corehq.apps.reports.dont_use.fields.SelectProgramField',
              'corehq.apps.reports.filters.dates.DatespanFilter']
    exportable = True
    emailable = True

    @property
    def headers(self):
        columns = [
            DataTablesColumn(_('Product')),
            DataTablesColumn(_('# Facilities')),
            DataTablesColumn(
                _('Stocked Out'),
                help_text=_("A facility is counted as stocked out when its \
                            stock is below the emergency level during the date \
                            range selected.")),
            DataTablesColumn(
                _('Understocked'),
                help_text=_("A facility is counted as under stocked when its \
                            stock is above the emergency level but below the \
                            low stock level during the date range selected.")),
            DataTablesColumn(
                _('Adequate Stock'),
                help_text=_("A facility is counted as adequately stocked when \
                            its stock is above the low level but below the \
                            overstock level during the date range selected.")),
            DataTablesColumn(
                _('Overstocked'),
                help_text=_("A facility is counted as overstocked when \
                            its stock is above the overstock level \
                            during the date range selected.")),
            #DataTablesColumn(_('Non-reporting')),
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
    def product_data(self):
        if getattr(self, 'prod_data', None) is None:
            self.prod_data = list(self.get_prod_data())
        return self.prod_data

    def get_prod_data(self):
        sp_ids = get_relevant_supply_point_ids(self.domain, self.active_location)

        stock_states = StockState.objects.filter(
            case_id__in=sp_ids,
            last_modified_date__lte=self.datespan.enddate_utc,
            last_modified_date__gte=self.datespan.startdate_utc,
            section_id=STOCK_SECTION_TYPE
        ).order_by('product_id')

        if self.program_id:
            stock_states = stock_states.filter(
                product_id__in=product_ids_filtered_by_program(
                    self.domain,
                    self.program_id
                )
            )

        product_grouping = {}
        for state in stock_states:
            status = state.stock_category
            if state.product_id in product_grouping:
                product_grouping[state.product_id][status] += 1
                product_grouping[state.product_id]['facility_count'] += 1

            else:
                product_grouping[state.product_id] = {
                    'obj': Product.get(state.product_id),
                    'stockout': 0,
                    'understock': 0,
                    'overstock': 0,
                    'adequate': 0,
                    'nodata': 0,
                    'facility_count': 1
                }
                product_grouping[state.product_id][status] = 1

        for product in product_grouping.values():
            yield [
                product['obj'].name,
                product['facility_count'],
                100.0 * product['stockout'] / product['facility_count'],
                100.0 * product['understock'] / product['facility_count'],
                100.0 * product['adequate'] / product['facility_count'],
                100.0 * product['overstock'] / product['facility_count'],
                100.0 * product['nodata'] / product['facility_count'],
            ]

    @property
    def rows(self):
        return [pd[0:2] + ['%.1f%%' % d for d in pd[2:]] for pd in self.product_data]

    def get_data_for_graph(self):
        ret = [
            {"key": "stocked out", "color": "#e00707"},
            {"key": "under stock", "color": "#ffb100"},
            {"key": "adequate stock", "color": "#4ac925"},
            {"key": "overstocked", "color": "#b536da"},
#            {"key": "nonreporting", "color": "#363636"},
            {"key": "unknown", "color": "#ABABAB"}
        ]
        statuses = ['stocked out', 'under stock', 'adequate stock', 'overstocked', 'no data'] #'nonreporting', 'no data']

        for r in ret:
            r["values"] = []

        for pd in self.product_data:
            for i, status in enumerate(statuses):
                ret[i]['values'].append({"x": pd[0], "y": pd[i+2]})

        return ret

    @property
    def charts(self):
        if 'location_id' in self.request.GET: # hack: only get data if we're loading an actual report
            chart = MultiBarChart(None, Axis(_('Products')), Axis(_('% of Facilities'), ',.1d'))
            chart.data = self.get_data_for_graph()
            return [chart]

class InventoryReport(GenericTabularReport, CommtrackReportMixin):
    name = ugettext_noop('Inventory')
    slug = StockStatusDataSource.slug
    fields = ['corehq.apps.reports.filters.fixtures.AsyncLocationFilter',
              'corehq.apps.reports.dont_use.fields.SelectProgramField',
              'corehq.apps.reports.filters.dates.DatespanFilter',]
    exportable = True
    emailable = True

    # temporary
    @classmethod
    def show_in_navigation(cls, domain=None, project=None, user=None):
        return super(InventoryReport, cls).show_in_navigation(domain, project, user) and _enabled_hack(domain)

    @property
    def headers(self):
        columns = [
            DataTablesColumn(_('Product')),
            DataTablesColumn(_('Stock on Hand'),
                help_text=_('Total stock on hand for all locations matching the filters.')),
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
    def product_data(self):
        if getattr(self, 'prod_data', None) is None:
            self.prod_data = []
            config = {
                'domain': self.domain,
                'location_id': self.request.GET.get('location_id'),
                'program_id': self.request.GET.get('program'),
                'startdate': self.datespan.startdate_utc,
                'enddate': self.datespan.enddate_utc,
                'aggregate': True
            }
            self.prod_data = self.prod_data + list(StockStatusDataSource(config).get_data())
        return self.prod_data

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

        for row in self.product_data:
            yield [
                fmt(row[StockStatusDataSource.SLUG_PRODUCT_NAME]),
                fmt(row[StockStatusDataSource.SLUG_CURRENT_STOCK]),
                fmt(row[StockStatusDataSource.SLUG_CONSUMPTION], int),
                fmt(row[StockStatusDataSource.SLUG_MONTHS_REMAINING], lambda k: '%.1f' % k),
                fmt(row[StockStatusDataSource.SLUG_CATEGORY], lambda k: statuses.get(k, k)),
                # fmt(row[StockStatusDataSource.SLUG_RESUPPLY_QUANTITY_NEEDED])
            ]


class ReportingRatesReport(GenericTabularReport, CommtrackReportMixin):
    name = ugettext_noop('Reporting Rate')
    slug = 'reporting_rate'
    fields = ['corehq.apps.reports.filters.fixtures.AsyncLocationFilter',
              'corehq.apps.reports.dont_use.fields.SelectProgramField',
              'corehq.apps.reports.filters.forms.FormsByApplicationFilter',
              'corehq.apps.reports.filters.dates.DatespanFilter',]
    exportable = True
    emailable = True

    # temporary
    @classmethod
    def show_in_navigation(cls, domain=None, project=None, user=None):
        return super(ReportingRatesReport, cls).show_in_navigation(domain, project, user) and _enabled_hack(domain)

    @property
    def headers(self):
        return DataTablesHeader(*(DataTablesColumn(text) for text in [
            _('Location'),
            _('# Sites'),
            _('# Reporting'),
            _('Reporting Rate'),
            _('# Non-reporting'),
            _('Non-reporting Rate'),
        ]))

    @property
    @memoized
    def _data(self):
        config = {
            'domain': self.domain,
            'location_id': self.request.GET.get('location_id'),
            'program_id': self.request.GET.get('program'),
            'startdate': self.datespan.startdate_utc,
            'enddate': self.datespan.enddate_utc,
            'request': self.request,
        }
        statuses = list(ReportingStatusDataSource(config).get_data())

        def child_loc(path):
            root = self.active_location
            ix = path.index(root._id) if root else -1
            try:
                return path[ix + 1]
            except IndexError:
                return None

        def case_iter():
            for site in statuses:
                if child_loc(site['loc_path']) is not None:
                    yield (site['loc_path'], site['reporting_status'])
        status_by_agg_site = map_reduce(lambda (path, status): [(child_loc(path), status)],
                                        data=case_iter())
        sites_by_agg_site = map_reduce(lambda (path, status): [(child_loc(path), path[-1])],
                                       data=case_iter())

        def status_tally(statuses):
            total = len(statuses)

            return map_reduce(lambda s: [(s,)],
                              lambda v: {'count': len(v), 'pct': len(v) / float(total)},
                              data=statuses)
        status_counts = dict((loc_id, status_tally(statuses))
                             for loc_id, statuses in status_by_agg_site.iteritems())

        master_tally = status_tally([site['reporting_status'] for site in statuses])

        locs = sorted(Location.view('_all_docs', keys=status_counts.keys(), include_docs=True),
                      key=lambda loc: loc.name)

        def fmt(pct):
            return '%.1f%%' % (100. * pct)

        def fmt_pct_col(loc, col_type):
            return fmt(status_counts[loc._id].get(col_type, {'pct': 0.})['pct'])

        def fmt_count_col(loc, col_type):
            return status_counts[loc._id].get(col_type, {'count': 0})['count']

        def _rows():
            for loc in locs:
                row = [loc.name, len(sites_by_agg_site[loc._id])]
                for k in ('reporting', 'nonreporting'):
                    row.append(fmt_count_col(loc, k))
                    row.append(fmt_pct_col(loc, k))

                yield row

        return master_tally, _rows()

    @property
    def rows(self):
        return self._data[1]

    def master_pie_chart_data(self):
        tally = self._data[0]
        labels = {
            'reporting': _('Reporting'),
            'nonreporting': _('Non-reporting'),
        }
        return [{'label': labels[k], 'value': tally.get(k, {'count': 0.})['count']} for k in ('reporting', 'nonreporting')]

    @property
    def charts(self):
        if 'location_id' in self.request.GET: # hack: only get data if we're loading an actual report
            return [PieChart(None, _('Current Reporting'), self.master_pie_chart_data())]


class RequisitionReport(CaseListReport):
    name = ugettext_noop('Requisition Report')
    slug = 'requisition_report'
    fields = ['corehq.apps.reports.filters.fixtures.AsyncLocationFilter',
              'corehq.apps.reports.filters.select.SelectOpenCloseFilter']
    exportable = True
    emailable = True
    asynchronous = True
    default_case_type = "commtrack-requisition"


    @classmethod
    def show_in_navigation(cls, domain=None, project=None, user=None):
        return super(RequisitionReport, cls).show_in_navigation() and user and user.is_previewer()

    @property
    @memoized
    def case_es(self):
        return CaseES(self.domain)

    @property
    def headers(self):
        return DataTablesHeader(*(DataTablesColumn(text) for text in [
                    _('Requisition Unique ID'),
                    _('Date Opened'),
                    _('Date Closed'),
                    _('Lead Time (Days)'),
                    _('Status'),
                ]))

    @classmethod
    def lead_time(self, closed_date, opened_date):
        try:
            closed_date = datetime.strptime(closed_date, "%Y-%m-%dT%H:%M:%SZ")
            opened_date = datetime.strptime(opened_date, "%Y-%m-%dT%H:%M:%SZ")
            days_rest_delta = (((closed_date - opened_date).seconds / 3600)*10)/24
            return "%s.%s" % ((closed_date - opened_date).days, days_rest_delta)
        except TypeError:
            return _("---")

    @property
    def case_filter(self):
        closed = self.request.GET.get('is_open')
        location_id = self.request.GET.get('location_id')
        filters = []
        or_stmt = []

        if closed:
            filters.append({'term': {'closed': True if closed == 'closed' else False}})

        if location_id:
            location = Location.get(location_id)
            if len(location.children) > 0:
                descedants_ids = [loc._id for loc in location.descendants]
                for loc_id in descedants_ids:
                    or_stmt.append({'term': {'location_': loc_id}})
                or_stmt = {'or': or_stmt}
                filters.append(or_stmt)
            else:
                filters.append({'term': {'location_': location_id}})

        return {'and': filters} if filters else {}

    @property
    def rows(self):
       for row in self.get_data():
            display = CaseDisplay(self, row['_case'])
            yield [
                display.case_id,
                display._dateprop('opened_on', iso=False),
                display._dateprop('closed_on', iso=False),
                self.lead_time(display.case['closed_on'], display.case['opened_on']),
                display.case['requisition_status']
            ]
