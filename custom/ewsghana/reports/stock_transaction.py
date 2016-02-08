from collections import OrderedDict
from casexml.apps.stock.models import StockTransaction
from corehq.apps.locations.models import SQLLocation
from corehq.apps.products.models import SQLProduct
from corehq.apps.reports.datatables import DataTablesHeader, DataTablesColumn
from corehq.apps.reports.filters.dates import DatespanFilter
from corehq.apps.reports.generic import GenericTabularReport
from custom.ewsghana.filters import EWSRestrictionLocationFilter, TransactionCheckboxFilter
from corehq.apps.reports.standard import CustomProjectReport, ProjectReportParametersMixin, DatespanMixin
from custom.ewsghana.filters import MultiProductFilter
from custom.ewsghana.utils import ews_date_format
from dimagi.utils.decorators.memoized import memoized


class StockTransactionReport(CustomProjectReport, GenericTabularReport,
                             ProjectReportParametersMixin, DatespanMixin):
    name = "Stock Transaction"
    slug = "export_stock_transaction"
    base_template = 'ewsghana/stock_transaction.html'
    exportable = True
    is_exportable = True
    fields = [EWSRestrictionLocationFilter, MultiProductFilter, DatespanFilter, TransactionCheckboxFilter]

    @property
    def location(self):
        return SQLLocation.objects.get(location_id=self.request.GET.get('location_id'))

    @property
    def split_by_product(self):
        return self.request.GET.get('split_by_product', False)

    @property
    def products(self):
        products = self.request.GET.getlist('product_id', [])
        if products:
            return SQLProduct.objects.filter(domain=self.domain,
                                             is_archived=False,
                                             product_id__in=products).order_by('code')
        return SQLProduct.objects.filter(domain=self.domain, is_archived=False).order_by('code')

    @property
    def headers(self):
        headers = DataTablesHeader(
            DataTablesColumn('Facility'),
            DataTablesColumn('Date of transaction submission'),
            DataTablesColumn('Transaction Type')
        )

        if self.split_by_product:
            headers.add_column(DataTablesColumn("Product"))
            headers.add_column(DataTablesColumn("Stock On Hand"))
            headers.add_column(DataTablesColumn("Consumption"))
        else:
            for product in self.products:
                headers.add_column(DataTablesColumn("{0} Stock on Hand".format(product.name)))
                headers.add_column(DataTablesColumn("{0} Consumption".format(product.name)))
        return headers

    @memoized
    def get_location_by_case_id(self, case_id):
        return SQLLocation.objects.get(domain=self.domain, supply_point_id=case_id)

    @property
    def rows(self):
        if self.location.location_type.administrative:
            supply_points = self.location.get_descendants().filter(
                location_type__administrative=False,
                is_archived=False).exclude(supply_point_id__isnull=True).values_list('supply_point_id', flat=True)
        else:
            supply_points = [self.location.supply_point_id]

        transactions = StockTransaction.objects.filter(
            case_id__in=supply_points,
            sql_product__in=self.products,
            report__date__range=[self.datespan.startdate,
                                 self.datespan.end_of_end_day]
        ).order_by('case_id', '-report__date', '-pk')

        if self.split_by_product:
            for transaction in transactions:
                location = self.get_location_by_case_id(transaction.case_id)
                yield [
                    location.name, ews_date_format(transaction.report.date), transaction.type,
                    transaction.sql_product.name, transaction.stock_on_hand, transaction.quantity
                ]
        else:
            product_dict = {p.code: idx for idx, p in enumerate(self.products)}
            rows = OrderedDict()
            for tr in transactions:
                key = (tr.case_id, tr.report.date.date(), tr.type)
                if key not in rows:
                    rows[key] = ['No Data'] * self.products.count() * 2
                product_idx = product_dict[tr.sql_product.code] * 2
                rows[key][product_idx] = tr.stock_on_hand
                rows[key][product_idx + 1] = tr.quantity if tr.quantity else 'No Data'

            for key, val in rows.iteritems():
                loc = SQLLocation.objects.get(supply_point_id=key[0])
                date = key[1]
                yield [
                    loc.name,
                    ews_date_format(date),
                    key[2]
                ] + val
