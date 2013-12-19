from corehq.apps.api.es import CaseES
from corehq.apps.commtrack.psi_hacks import is_psi_domain
from corehq.apps.reports.commtrack.data_sources import StockStatusDataSource, ReportingStatusDataSource, is_timely
from corehq.apps.reports.generic import GenericTabularReport
from corehq.apps.reports.commtrack.psi_prototype import CommtrackReportMixin
from corehq.apps.reports.datatables import DataTablesHeader, DataTablesColumn
from corehq.apps.commtrack.models import Product, SupplyPointProductCase as SPPCase
from corehq.apps.reports.graph_models import PieChart, MultiBarChart, Axis
from dimagi.utils.couch.loosechange import map_reduce
from datetime import datetime
from corehq.apps.locations.models import Location
from dimagi.utils.decorators.memoized import memoized
from django.utils.translation import ugettext as _, ugettext_noop
from corehq.apps.reports.standard.cases.basic import CaseListReport
from corehq.apps.reports.standard.cases.data_sources import CaseDisplay

def _enabled_hack(domain):
    return not is_psi_domain(domain)

class CurrentStockStatusReport(GenericTabularReport, CommtrackReportMixin):
    name = ugettext_noop('Stock Status by Product')
    slug = 'current_stock_status'
    fields = ['corehq.apps.reports.fields.AsyncLocationField']
    exportable = True
    emailable = True

    @property
    def headers(self):
        return DataTablesHeader(*(DataTablesColumn(text) for text in [
                    _('Product'),
                    _('# Facilities'),
                    _('Stocked Out'),
                    _('Understocked'),
                    _('Adequate Stock'),
                    _('Overstocked'),
                    #_('Non-reporting'),
                    _('Insufficient Data'),
                ]))

    @property
    def product_data(self):
        if getattr(self, 'prod_data', None) is None:
            self.prod_data = list(self.get_prod_data())
        return self.prod_data

    def get_prod_data(self):
        startkey = [self.domain, self.active_location._id if self.active_location else None]
        product_cases = SPPCase.view('commtrack/product_cases', startkey=startkey, endkey=startkey + [{}], include_docs=True)

        cases_by_product = map_reduce(lambda c: [(c.product,)], data=product_cases, include_docs=True)
        products = Product.view('_all_docs', keys=cases_by_product.keys(), include_docs=True)

        def status(case):
            return case.current_stock_category if is_timely(case, 1000) else 'nonreporting'

        status_by_product = dict((p, map_reduce(lambda c: [(status(c),)], len, data=cases)) for p, cases in cases_by_product.iteritems())

        cols = ['stockout', 'understock', 'adequate', 'overstock', 'nodata'] #'nonreporting', 'nodata']
        for p in sorted(products, key=lambda p: p.name):
            cases = cases_by_product.get(p._id, [])
            results = status_by_product.get(p._id, {})
            def val(key):
                return results.get(key, 0) / float(len(cases))
            yield [p.name, len(cases)] + [100. * val(key) for key in cols]

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

class AggregateStockStatusReport(GenericTabularReport, CommtrackReportMixin):
    name = ugettext_noop('Inventory')
    slug = StockStatusDataSource.slug
    fields = ['corehq.apps.reports.fields.AsyncLocationField']
    exportable = True
    emailable = True

    # temporary
    @classmethod
    def show_in_navigation(cls, domain=None, project=None, user=None):
        return super(AggregateStockStatusReport, cls).show_in_navigation(domain, project, user) and _enabled_hack(domain)

    @property
    def headers(self):
        return DataTablesHeader(*(DataTablesColumn(text) for text in [
                    _('Product'),
                    _('Total SOH'),
                    _('Total AMC'),
                    _('Remaining MOS'),
                    _('Stock Status'),
                ]))

    @property
    def product_data(self):
        if getattr(self, 'prod_data', None) is None:
            config = {
                'domain': self.domain,
                'location_id': self.request.GET.get('location_id'),
                'aggregate': True
            }
            self.prod_data = list(StockStatusDataSource(config).get_data())
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
                    fmt(row[StockStatusDataSource.SLUG_CATEGORY], lambda k: statuses.get(k, k))
                ]


class ReportingRatesReport(GenericTabularReport, CommtrackReportMixin):
    name = ugettext_noop('Reporting Rate')
    slug = 'reporting_rate'
    fields = ['corehq.apps.reports.fields.AsyncLocationField',
              'corehq.apps.reports.filters.dates.DatespanFilter']
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
                    _('On-time'),
                    _('Late'),
                    _('Non-reporting'),
                ]))

    @property
    @memoized
    def _data(self):
        config = {
            'domain': self.domain,
            'location_id': self.request.GET.get('location_id'),
            'start_date': self.request.GET.get('startdate'),
            'end_date': self.request.GET.get('enddate'),
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
        def fmt_col(loc, col_type):
            return fmt(status_counts[loc._id].get(col_type, {'pct': 0.})['pct'])
        def _rows():
            for loc in locs:
                num_sites = len(sites_by_agg_site[loc._id])
                yield [loc.name, len(sites_by_agg_site[loc._id])] + [fmt_col(loc, k) for k in ('ontime', 'late', 'nonreporting')]

        return master_tally, _rows()

    @property
    def rows(self):
        return self._data[1]

    def master_pie_chart_data(self):
        tally = self._data[0]
        labels = {
            'ontime': _('On-time'),
            'late': _('Late'),
            'nonreporting': _('Non-reporting'),
        }
        return [{'label': labels[k], 'value': tally.get(k, {'count': 0.})['count']} for k in ('ontime', 'late', 'nonreporting')]

    @property
    def charts(self):
        if 'location_id' in self.request.GET: # hack: only get data if we're loading an actual report
            return [PieChart(None, _('Current Reporting'), self.master_pie_chart_data())]


class RequisitionReport(CaseListReport):
    name = ugettext_noop('Requisition Report')
    slug = 'requisition_report'
    fields = ['corehq.apps.reports.fields.AsyncLocationField', 'corehq.apps.reports.fields.SelectOpenCloseField']
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
                    _('Lead Time'),
                    _('Status'),
                ]))

    @classmethod
    def lead_time(self, closed_date, opened_date):
        try:
            closed_date = datetime.strptime(closed_date, "%Y-%m-%dT%H:%M:%SZ")
            opened_date = datetime.strptime(opened_date, "%Y-%m-%dT%H:%M:%SZ")
            return str(closed_date - opened_date)
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