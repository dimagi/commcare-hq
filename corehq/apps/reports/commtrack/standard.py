from corehq.apps.reports.standard import ProjectReport, ProjectReportParametersMixin, DatespanMixin
from corehq.apps.reports.generic import GenericTabularReport
from corehq.apps.reports.commtrack.psi_prototype import CommtrackReportMixin
from corehq.apps.reports.datatables import DataTablesHeader, DataTablesColumn
from casexml.apps.case.models import CommCareCase
from corehq.apps.commtrack.models import Product
from dimagi.utils.couch.loosechange import map_reduce
from corehq.apps.commtrack.util import num_periods_late

# TODO make settings

UNDERSTOCK_THRESHOLD = 0.5 # months
OVERSTOCK_THRESHOLD = 2. # months

REPORTING_PERIOD = 'weekly'
REPORTING_PERIOD_ARGS = (1,)

def current_stock(case):
    current_stock = getattr(case, 'current_stock', None)
    if current_stock is not None:
        current_stock = int(current_stock)
    return current_stock

def monthly_consumption(case):
    daily_rate = case.computed_.get('commtrack', {}).get('consumption_rate')
    if daily_rate is None:
        daily_rate = default_consumption(case)
    if daily_rate is None:
        return None

    monthly_rate = daily_rate * 365.2425 / 12.
    return monthly_rate

def default_consumption(case):
    # TODO get a fallback consumption rate based on product/facility type
    # if setting is monthly rate, must normalize to daily
    return None

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


class CurrentStockStatusReport(GenericTabularReport, CommtrackReportMixin):
    name = 'Current Stock Status by Product'
    slug = 'current_stock_status'
    fields = ['corehq.apps.reports.fields.AsyncLocationField']
    exportable = True
    emailable = True

    report_template_path = "reports/async/tabular_graph.html"

    @property
    def headers(self):
        return DataTablesHeader(*(DataTablesColumn(text) for text in [
                    'Product',
                    'Stocked Out',
                    'Understocked',
                    'Adequate Stock',
                    'Overstocked',
                    'Non-reporting',
                    'Insufficient Data',
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
            return case_stock_category(case) if num_periods_late(case, REPORTING_PERIOD, *REPORTING_PERIOD_ARGS) == 0 else 'nonreporting'

        status_by_product = dict((p, map_reduce(lambda c: [(status(c),)], len, data=cases)) for p, cases in cases_by_product.iteritems())

        cols = ['stockout', 'understock', 'adequate', 'overstock', 'nonreporting', 'nodata']
        for p in sorted(products, key=lambda p: p.name):
            cases = cases_by_product.get(p._id, [])
            results = status_by_product.get(p._id, {})
            def val(key):
                return results.get(key, 0) / float(len(cases))
            yield [p.name] + [100. * val(key) for key in cols]

    @property
    def rows(self):
        return [[pd[0]] + ['%.1f%%' %d for d in pd[1:]] for pd in self.product_data]


    def get_data_for_graph(self):
        ret = [
            {"key": "stocked out", "color": "#e00707"},
            {"key": "under stock", "color": "#ffb100"},
            {"key": "adequate stock", "color": "#4ac925"},
            {"key": "overstocked", "color": "#b536da"},
            {"key": "nonreporting", "color": "#363636"},
            {"key": "no data", "color": "#ABABAB"}
        ]
        statuses = ['stocked out', 'under stock', 'adequate stock', 'overstocked', 'nonreporting', 'no data']

        for r in ret:
            r["values"] = []

        for pd in self.product_data:
            for i, status in enumerate(statuses):
                ret[i]['values'].append({"x": pd[0], "y": pd[i+1]})

        return ret

    @property
    def report_context(self):
        ctxt = super(CurrentStockStatusReport, self).report_context
        if 'location_id' in self.request.GET: # hack: only get data if we're loading an actual report
            ctxt['stock_data'] = self.get_data_for_graph()
        return ctxt

class AggregateStockStatusReport(GenericTabularReport, CommtrackReportMixin):
    name = 'Aggregate Stock Status by Product'
    slug = 'agg_stock_status'
    fields = ['corehq.apps.reports.fields.AsyncLocationField']
    exportable = True
    emailable = True

    #report_template_path = "reports/async/tabular_graph.html"

    @property
    def headers(self):
        return DataTablesHeader(*(DataTablesColumn(text) for text in [
                    'Product',
                    'Total SOH',
                    'Total AMC',
                    'Remaining MOS',
                    'Stock Status',
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
            data = [(current_stock(c), monthly_consumption(c)) for c in cases]
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

            for row in self.product_data:
                row[1] = fmt(row[1])
                row[2] = fmt(row[2], int)
                row[3] = fmt(row[3], lambda k: '%.1f' % k)
                row[4] = fmt(row[4])
                yield row

    """
    def get_data_for_graph(self):
        ret = [
            {"key": "stocked out", "color": "#e00707"},
            {"key": "under stock", "color": "#ffb100"},
            {"key": "adequate stock", "color": "#4ac925"},
            {"key": "overstocked", "color": "#b536da"},
            {"key": "nonreporting", "color": "#363636"},
            {"key": "no data", "color": "#ABABAB"}
        ]
        statuses = ['stocked out', 'under stock', 'adequate stock', 'overstocked', 'nonreporting', 'no data']

        for r in ret:
            r["values"] = []

        for pd in self.product_data:
            for i, status in enumerate(statuses):
                ret[i]['values'].append({"x": pd[0], "y": pd[i+1]})

        return ret

    @property
    def report_context(self):
        ctxt = super(CurrentStockStatusReport, self).report_context
        if 'location_id' in self.request.GET: # hack: only get data if we're loading an actual report
            ctxt['stock_data'] = self.get_data_for_graph()
        return ctxt
    """
