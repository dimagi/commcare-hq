from corehq.apps.reports.standard import ProjectReport, ProjectReportParametersMixin, DatespanMixin
from corehq.apps.reports.generic import GenericTabularReport
from corehq.apps.reports.commtrack.psi_prototype import CommtrackReportMixin
from corehq.apps.reports.datatables import DataTablesHeader, DataTablesColumn
from casexml.apps.case.models import CommCareCase
from corehq.apps.commtrack.models import Product
from dimagi.utils.couch.loosechange import map_reduce

UNDERSTOCK_THRESHOLD = 0.5 # months
OVERSTOCK_THRESHOLD = 2. # months

class CurrentStockStatusReport(GenericTabularReport, CommtrackReportMixin):
    name = 'Current Stock Status by Product'
    slug = 'current_stock_status'
    fields = ['corehq.apps.reports.fields.AsyncLocationField']
    exportable = True
    emailable = True

    @property
    def headers(self):
        return DataTablesHeader(*(DataTablesColumn(text) for text in [
                    'Product',
                    'Stocked Out',
                    'Understocked',
                    'Adequate Stock',
                    'Overstocked',
                    'Non-reporting',
                ]))

    @property
    def rows(self):
        startkey = [self.domain, self.active_location._id if self.active_location else None]
        product_cases = CommCareCase.view('commtrack/product_cases', startkey=startkey, endkey=startkey + [{}], include_docs=True)

        cases_by_product = map_reduce(lambda c: [(c.product,)], data=product_cases, include_docs=True)
        products = Product.view('_all_docs', keys=cases_by_product.keys(), include_docs=True)

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

        def stock_category(case):
            current_stock = getattr(case, 'current_stock', None)
            if current_stock is None:
                return 'nodata'
            current_stock = int(current_stock)
            consumption_rate = monthly_consumption(case)

            if current_stock == 0:
                return 'stockout'
            elif consumption_rate is None:
                return 'nodata'

            months_left = current_stock / consumption_rate
            if months_left < get_threshold('low'):
                return 'understock'
            elif months_left > get_threshold('high'):
                return 'overstock'
            else:
                return 'adequate'

        # TODO handle non-reporting

        status_by_product = dict((p, map_reduce(lambda c: [(stock_category(c),)], len, data=cases)) for p, cases in cases_by_product.iteritems())

        cols = ['stockout', 'understock', 'adequate', 'overstock', 'nodata']
        for p in sorted(products, key=lambda p: p.name):
            cases = cases_by_product.get(p._id, [])
            results = status_by_product.get(p._id, {})
            def val(key):
                return results.get(key, 0) / float(len(cases))
            yield [p.name] + ['%.1f%%' % (100. * val(key)) for key in cols]

