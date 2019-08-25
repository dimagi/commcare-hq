from collections import defaultdict

from casexml.apps.stock.models import StockTransaction
from corehq.apps.commtrack.models import StockState
from corehq.apps.locations.models import SQLLocation
from corehq.apps.products.models import SQLProduct
from corehq.apps.reports.commtrack.const import STOCK_SECTION_TYPE
from corehq.apps.reports.datatables import DataTablesHeader, DataTablesColumn
from custom.ewsghana.filters import EWSDateFilter, EWSRestrictionLocationFilter
from custom.ewsghana.reports import EWSData, MultiReport
from django.utils.translation import ugettext as _
from custom.ewsghana.utils import get_descendants, get_country_id, ews_date_format
from memoized import memoized
import six


class EmailReportData(EWSData):
    show_table = True
    use_datatables = True

    def get_locations(self, loc_id, domain):
        return []


class StockSummaryReportData(EmailReportData):
    slug = 'stock_summary'

    @property
    def headers(self):
        return DataTablesHeader(*[
            DataTablesColumn(_('Product')),
            DataTablesColumn(_('Total # Facilities Registered with this Product')),
            DataTablesColumn(_('Total # facilities reported')),
            DataTablesColumn(_('% Facilities with Stockouts')),
            DataTablesColumn(_('% Facilities with Adequate Stock')),
            DataTablesColumn(_('% Facilities with Low Stock')),
            DataTablesColumn(_('% Facilities Overstocked')),
        ])

    def _last_transaction_for_product_in_period(self):
        transactions = StockTransaction.objects.filter(
            report__domain=self.domain,
            report__date__range=(self.config['startdate'], self.config['enddate']),
            type__in=['stockonhand', 'stockout']
        ).distinct('case_id', 'product_id').order_by('case_id', 'product_id', '-report__date', '-pk')
        location_to_transactions = defaultdict(list)
        for transaction in transactions:
            location_to_transactions[transaction.case_id].append(transaction)
        return location_to_transactions

    @property
    def rows(self):
        def percent(x, y):
            return "%d%% <small>(%d)</small>" % (x * 100 / (y or 1), x)

        def _stock_status(transaction, daily_consumption, loc):
            state = transaction.stock_on_hand / ((daily_consumption * 30) or 1)
            if state == 0.0:
                return "stockout"
            elif state < loc.location_type.understock_threshold:
                return "adequate"
            elif state < loc.location_type.overstock_threshold + 7:
                return "low"
            else:
                return "overstock"

        locations = self.get_locations(self.config['location_id'], self.config['domain'])

        row_data = {}

        for product in SQLProduct.by_domain(self.domain).exclude(is_archived=True):
            row_data[product.name] = {'total_fac': 0, 'reported_fac': 0,
                                      'stockout': 0, 'low': 0, 'overstock': 0, 'adequate': 0}

        transactions = self._last_transaction_for_product_in_period()
        stock_states = StockState.objects.filter(
            sql_location__in=locations
        ).values_list('case_id', 'product_id', 'daily_consumption')

        location_product_to_consumption = {
            (case_id, product_id): daily_consumption or 0
            for case_id, product_id, daily_consumption in stock_states
        }

        for location in locations:
            location_products = list(location.products.exclude(is_archived=True))

            for product in location_products:
                row_data[product.name]['total_fac'] += 1

            for transaction in transactions.get(location.supply_point_id, []):
                sql_product = transaction.sql_product
                if sql_product not in location_products:
                    continue
                p_name = sql_product.name
                row_data[p_name]['reported_fac'] += 1
                daily_consumption = location_product_to_consumption.get(
                    (location.supply_point_id, transaction.product_id), 0
                )
                s = _stock_status(transaction, daily_consumption, location)
                row_data[p_name][s] += 1

        rows = []
        for k, v in six.iteritems(row_data):
            if v['total_fac'] > 0:
                rows.append([
                    k,
                    v['total_fac'],
                    v['reported_fac'],
                    percent(v['stockout'], v['reported_fac']),
                    percent(v['adequate'], v['reported_fac']),
                    percent(v['low'], v['reported_fac']),
                    percent(v['overstock'], v['reported_fac']),
                ])
        return rows

    def get_locations(self, loc_id, domain):
        return get_descendants(loc_id)


class CMSRMSReportData(EmailReportData):
    title = 'Weekly Stock Summary Report - CMS and RMS'
    slug = 'stock_summary'

    @property
    def headers(self):
        headers = DataTablesHeader(*[
            DataTablesColumn(_('Product')),
            DataTablesColumn(_('Total # facilities registered with this product')),
            DataTablesColumn(_('Total # facilities reported')),
            DataTablesColumn(_('% Facilities with stockouts'))
        ])

        for location in self.get_locations(self.config['location_id'], self.config['domain']).order_by('name'):
            headers.add_column(DataTablesColumn(location.name))
        headers.add_column(DataTablesColumn(_('Total Stock')))
        return headers

    @property
    def rows(self):
        def percent(x, y):
            return "%d%% <small>(%d)</small>" % (x * 100 / (y or 1), x)

        locations = self.get_locations(self.config['location_id'], self.config['domain'])

        products = self.unique_products(locations)
        row_data = {product.name: defaultdict(lambda: 0) for product in products}

        for location in locations:
            stock_transactions = StockTransaction.objects.filter(
                case_id=location.supply_point_id,
                section_id=STOCK_SECTION_TYPE,
                sql_product__in=products,
                report__date__range=[
                    self.config['startdate'],
                    self.config['enddate']
                ]
            ).distinct('product_id').order_by('product_id', '-report__date')

            for stock_transaction in stock_transactions:
                p_name = stock_transaction.sql_product.name
                row_data[p_name]['reported_fac'] += 1
                if not stock_transaction.stock_on_hand:
                    row_data[p_name]['fac_with_stockout'] += 1
                row_data[p_name][location.pk] = int(stock_transaction.stock_on_hand)
                row_data[p_name]['total'] += int(stock_transaction.stock_on_hand)
            for product in location.products:
                row_data[product.name]['total_fac'] += 1

        rows = []
        for k, v in six.iteritems(row_data):
            row = [
                k,
                v['total_fac'],
                v['reported_fac'],
                percent(v['fac_with_stockout'], v['total_fac'])
            ]
            for location in locations.order_by('name'):
                row.append(v[location.pk])
            row.append(v['total'])
            rows.append(row)
        return rows

    def get_locations(self, loc_id, domain):
        return SQLLocation.objects.filter(
            location_type__name__in=['Regional Medical Store', 'Central Medical Store'],
            domain=domain, is_archived=False
        )


class EmailReportingData(EWSData):
    title = "Reporting"
    slug = "reporting"
    show_table = True

    def get_locations(self, loc_id, domain):
        return []

    @property
    def headers(self):
        return DataTablesHeader(*[])

    @property
    def rows(self):
        def percent(x, y, text):
            return "%d%s<small> (%d/%d)</small>" % (x * 100 / (y or 1), text, x, y)

        locations = self.location.get_descendants().exclude(is_archived=True, location_type__administrative=True)
        reported = StockTransaction.objects.filter(
            case_id__in=[location.supply_point_id for location in locations],
            report__date__range=[self.config['startdate'], self.config['enddate']]
        ).distinct('case_id').count()
        completed = 0
        for loc in locations:
            products = set(
                loc.products.values_list('product_id', flat=True)
            )
            st = set(StockTransaction.objects.filter(
                case_id=loc.supply_point_id,
                report__date__range=[self.config['startdate'], self.config['enddate']]
            ).distinct('product_id').values_list('product_id', flat=True))
            if len(products) != 0 and not products - st:
                completed += 1

        return [[percent(reported, len(locations), '% of facilities are reporting'),
                 percent(completed, reported, '% of submitted reports are complete')]]


class StockSummaryReportingData(EmailReportingData):

    def get_locations(self, loc_id, domain):
        return [loc.supply_point_id for loc in get_descendants(loc_id)]


class CMSRMSSummaryReportingData(EmailReportingData):

    def get_locations(self, loc_id, domain):
        return [
            loc.supply_point_id
            for loc in SQLLocation.objects.filter(
                location_type__name__in=['Regional Medical Store', 'Central Medical Store'],
                domain=domain, is_archived=False
            )
        ]


class StockSummaryReport(MultiReport):
    fields = [EWSRestrictionLocationFilter, EWSDateFilter]
    name = "Stock Summary"
    slug = 'stock_summary_report'
    exportable = False
    is_exportable = False
    split = False

    @property
    @memoized
    def location(self):
        location = super(StockSummaryReport, self).location
        if location.location_type.administrative:
            return location
        return self.root_location

    @property
    def title(self):
        return 'Weekly Stock Summary Report - {0} - {1} {2}'.format(
            self.location.name,
            ews_date_format(self.datespan.startdate_utc),
            ews_date_format(self.datespan.enddate_utc)
        )

    @property
    def report_config(self):
        report_config = super(StockSummaryReport, self).report_config
        report_config.update(dict(
            startdate=self.datespan.startdate_utc,
            enddate=self.datespan.enddate_utc,
            program='',
            products=''
        ))
        return report_config

    @property
    @memoized
    def data_providers(self):
        return [StockSummaryReportingData(self.report_config),
                StockSummaryReportData(self.report_config)]

    @classmethod
    def show_in_navigation(cls, domain=None, project=None, user=None):
        return True


class CMSRMSReport(MultiReport):
    fields = [EWSDateFilter]
    name = "CMS and RMS Summary"
    slug = 'cms_rms_summary_report'
    exportable = True
    is_exportable = True
    split = False

    @property
    def title(self):
        return 'Weekly Stock Summary Report - CMS and RMS - {0} {1}'.format(
            ews_date_format(self.datespan.startdate_utc),
            ews_date_format(self.datespan.enddate_utc)
        )

    @property
    def report_config(self):
        return dict(
            domain=self.domain,
            startdate=self.datespan.startdate_utc,
            enddate=self.datespan.enddate_utc,
            location_id=get_country_id(self.domain),
            program='',
            products=''
        )

    @property
    @memoized
    def data_providers(self):
        return [CMSRMSSummaryReportingData(self.report_config),
                CMSRMSReportData(self.report_config)]

    @classmethod
    def show_in_navigation(cls, domain=None, project=None, user=None):
        return True
