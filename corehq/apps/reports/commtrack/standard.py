from corehq.apps.commtrack.psi_hacks import is_psi_domain
from corehq.apps.reports.generic import GenericTabularReport
from corehq.apps.reports.commtrack.psi_prototype import CommtrackReportMixin
from corehq.apps.reports.datatables import DataTablesHeader, DataTablesColumn
from casexml.apps.case.models import CommCareCase
from corehq.apps.commtrack.models import Product
from corehq.apps.reports.graph_models import PieChart, MultiBarChart, Axis
from dimagi.utils.couch.loosechange import map_reduce
from corehq.apps.commtrack.util import num_periods_late
from datetime import date, datetime
from corehq.apps.locations.models import Location
from dimagi.utils.decorators.memoized import memoized
from django.utils.translation import ugettext as _, ugettext_noop

DAYS_PER_MONTH = 365.2425 / 12.

# TODO make settings

UNDERSTOCK_THRESHOLD = 0.5 # months
OVERSTOCK_THRESHOLD = 2. # months

REPORTING_PERIOD = 'weekly'
REPORTING_PERIOD_ARGS = (1,)

DEFAULT_CONSUMPTION = 10. # per month

def current_stock(case):
    """helper method to get current product stock -- TODO move to wrapper class"""
    current_stock = getattr(case, 'current_stock', None)
    if current_stock is not None:
        current_stock = int(current_stock)
    return current_stock

def monthly_consumption(case):
    """get monthly consumption rate for a product at a given location"""
    daily_rate = case.computed_.get('commtrack', {}).get('consumption_rate')
    if daily_rate is None:
        daily_rate = default_consumption(case) / DAYS_PER_MONTH
    if daily_rate is None:
        return None

    monthly_rate = daily_rate * DAYS_PER_MONTH
    return monthly_rate

def default_consumption(case):
    """get default monthly consumption rate for when real-world computed rate is
    not available"""
    # TODO pull this from a configurable setting
    # TODO allow more granular defaulting based on product/facility type etc
    return DEFAULT_CONSUMPTION

def is_timely(case, limit=0):
    return num_periods_late(case, REPORTING_PERIOD, *REPORTING_PERIOD_ARGS) <= limit

def reporting_status(case):
    if is_timely(case):
        return 'ontime'
    elif is_timely(case, 1):
        return 'late'
    else:
        return 'nonreporting'

def get_threshold(type):
    # TODO vary by supply point type?
    return {
        'low': UNDERSTOCK_THRESHOLD,
        'high': OVERSTOCK_THRESHOLD,
    }[type]

def stock_category(stock, consumption, months_left=None):
    if stock is None:
        return 'nodata'
    elif stock == 0:
        return 'stockout'
    elif consumption is None:
        return 'nodata'
    elif consumption == 0:
        return 'overstock'

    if months_left is None:
        months_left = stock / consumption

    if months_left is None:
        return 'nodata'
    elif months_left < get_threshold('low'):
        return 'understock'
    elif months_left > get_threshold('high'):
        return 'overstock'
    else:
        return 'adequate'

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
        product_cases = CommCareCase.view('commtrack/product_cases', startkey=startkey, endkey=startkey + [{}], include_docs=True)

        cases_by_product = map_reduce(lambda c: [(c.product,)], data=product_cases, include_docs=True)
        products = Product.view('_all_docs', keys=cases_by_product.keys(), include_docs=True)

        def case_stock_category(case):
            return stock_category(current_stock(case), monthly_consumption(case))
        def status(case):
            return case_stock_category(case) if is_timely(case, 1000) else 'nonreporting'

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
        return [pd[0:2] + ['%.1f%%' %d for d in pd[2:]] for pd in self.product_data]

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
    name = ugettext_noop('Consumption and Months Remaining')
    slug = 'agg_stock_status'
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
            self.prod_data = list(self.get_prod_data())
        return self.prod_data

    def get_prod_data(self):
        startkey = [self.domain, self.active_location._id if self.active_location else None]
        product_cases = CommCareCase.view('commtrack/product_cases', startkey=startkey, endkey=startkey + [{}], include_docs=True)

        cases_by_product = map_reduce(lambda c: [(c.product,)], data=product_cases, include_docs=True)
        products = Product.view('_all_docs', keys=cases_by_product.keys(), include_docs=True)

        def _sum(vals):
            return sum(vals) if vals else None

        def aggregate_product(cases):
            data = [(current_stock(c), monthly_consumption(c)) for c in cases if is_timely(c, 1000)]
            total_stock = _sum([d[0] for d in data if d[0] is not None])
            total_consumption = _sum([d[1] for d in data if d[1] is not None])
            # exclude stock values w/o corresponding consumption figure from total months left calculation
            consumable_stock = _sum([d[0] for d in data if d[0] is not None and d[1] is not None])
            try:
                months_left = consumable_stock / total_consumption
            except (TypeError, ZeroDivisionError):
                months_left = None

            return {
                'total_stock': total_stock,
                'total_consumption': total_consumption,
                'months_left': months_left,
            }

        status_by_product = dict((p, aggregate_product(cases)) for p, cases in cases_by_product.iteritems())
        for p in sorted(products, key=lambda p: p.name):
            stats = status_by_product[p._id]
            yield [
                p.name,
                stats['total_stock'],
                stats['total_consumption'],
                stats['months_left'],
                stock_category(stats['total_stock'], stats['total_consumption'], stats['months_left']),
            ]

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
                row[1] = fmt(row[1])
                row[2] = fmt(row[2], int)
                row[3] = fmt(row[3], lambda k: '%.1f' % k)
                row[4] = fmt(row[4], lambda k: statuses.get(k, k))
                yield row

class ReportingRatesReport(GenericTabularReport, CommtrackReportMixin):
    name = ugettext_noop('Reporting Rate')
    slug = 'reporting_rate'
    fields = ['corehq.apps.reports.fields.AsyncLocationField']
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
        startkey = [self.domain, self.active_location._id if self.active_location else None]
        product_cases = CommCareCase.view('commtrack/product_cases', startkey=startkey, endkey=startkey + [{}], include_docs=True)

        def latest_case(cases):
            # getting last report date should probably be moved to a util function in a case wrapper class
            return max(cases, key=lambda c: getattr(c, 'last_reported', datetime(2000, 1, 1)).date())
        cases_by_site = map_reduce(lambda c: [(tuple(c.location_),)],
                                   lambda v: reporting_status(latest_case(v)),
                                   data=product_cases, include_docs=True)

        def child_loc(path):
            root = self.active_location
            ix = path.index(root._id) if root else -1
            try:
                return path[ix + 1]
            except IndexError:
                return None
        def case_iter():
            for k, v in cases_by_site.iteritems():
                if child_loc(k) is not None:
                    yield (k, v)
        status_by_agg_site = map_reduce(lambda (path, status): [(child_loc(path), status)],
                                        data=case_iter())
        sites_by_agg_site = map_reduce(lambda (path, status): [(child_loc(path), path[-1])],
                                       data=case_iter())

        def status_tally(statuses):
            total = len(statuses)
            return map_reduce(lambda s: [(s,)], lambda v: {'count': len(v), 'pct': len(v) / float(total)}, data=statuses)
        status_counts = dict((loc_id, status_tally(statuses)) for loc_id, statuses in status_by_agg_site.iteritems())

        master_tally = status_tally(cases_by_site.values())

        locs = sorted(Location.view('_all_docs', keys=status_counts.keys(), include_docs=True), key=lambda loc: loc.name)
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
        return [{
                'key': _('Current Reporting'),
                'values': [{'label': labels[k], 'value': tally.get(k, {'count': 0.})['count']} for k in ('ontime', 'late', 'nonreporting')],
        }]

    @property
    def charts(self):
        if 'location_id' in self.request.GET: # hack: only get data if we're loading an actual report
            return [PieChart(None, self.master_pie_chart_data())]