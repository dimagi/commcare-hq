from collections import defaultdict
from casexml.apps.stock.models import StockTransaction
from corehq.apps.commtrack.models import StockState, CommtrackConfig
from corehq.apps.locations.models import SQLLocation
from corehq.apps.products.models import SQLProduct
from corehq.apps.reports.commtrack.const import STOCK_SECTION_TYPE
from corehq.apps.reports.datatables import DataTablesHeader, DataTablesColumn
from corehq.apps.reports.filters.fixtures import AsyncLocationFilter
from corehq.apps.reports.filters.dates import DatespanFilter
from custom.ewsghana.reports import EWSData, MultiReport
from django.utils.translation import ugettext as _
from custom.ewsghana.utils import get_supply_points, get_country_id
from dimagi.utils.decorators.memoized import memoized


class EmailReportData(EWSData):
    show_table = True
    use_datatables = True

    def get_locations(self, loc_id, domain):
        return []

    @property
    def headers(self):
        return DataTablesHeader(*[
            DataTablesColumn(_('Product')),
            DataTablesColumn(_('% Facilities with Stockouts')),
            DataTablesColumn(_('Total # Facilities Registered with this Product')),
            DataTablesColumn(_('Total Stock')),
            DataTablesColumn(_('% Facilities with Consumption Data')),
            DataTablesColumn(_('Monthly Consumption')),
            DataTablesColumn(_('Months of Stock')),
            DataTablesColumn(_('Stock Status'))
        ])

    @property
    def rows(self):
        def percent(x, y):
            return "%d%% (%d)" % (x * 100 / (y or 1), x)

        def stock_status(status):
            stock_levels = CommtrackConfig.for_domain(self.config['domain']).stock_levels_config
            if status == 0.0:
                return 'Stockout'
            elif status < stock_levels.understock_threshold:
                return 'Low'
            elif status < stock_levels.overstock_threshold:
                return 'Adequate'
            else:
                return 'Overstock'

        locations = self.get_locations(self.config['location_id'], self.config['domain'])

        products = self.unique_products(locations)
        row_data = {product.name: defaultdict(lambda: 0) for product in products}

        for location in locations:
            stock_states = StockState.objects.filter(
                case_id=location.supply_point_id,
                section_id=STOCK_SECTION_TYPE,
                sql_product__in=products
            )

            for state in stock_states:
                p_name = state.sql_product.name
                row_data[p_name]['total_fac'] += 1
                if state.stock_on_hand:
                    row_data[p_name]['total_stock'] += state.stock_on_hand
                else:
                    row_data[p_name]['fac_with_stockout'] += 1
                if state.get_monthly_consumption():
                    row_data[p_name]['fac_with_consumption'] += 1
                    row_data[p_name]['monthly_consumption'] += state.get_monthly_consumption()

        rows = []
        for k, v in row_data.iteritems():
            months_of_stock = float(v['total_stock']) / float(v['monthly_consumption'] or 1)
            rows.append([k, percent(v['fac_with_stockout'], v['total_fac']),
                        v['total_fac'], v['total_stock'], percent(v['fac_with_consumption'], v['total_fac']),
                        v['monthly_consumption'], "%.1f" % months_of_stock, stock_status(months_of_stock)])
        return rows


class StockSummaryReportData(EmailReportData):
    slug = 'stock_summary'

    @property
    def title(self):
        return 'Weekly Stock Summary Report - ' + SQLLocation.objects.get(
            location_id=self.config['location_id']).name

    def get_locations(self, loc_id, domain):
        return get_supply_points(loc_id, domain)


class CMSRMSReportData(EmailReportData):
    title = 'Weekly Stock Summary Report - CMS and RMS'
    slug = 'stock_summary'

    def get_locations(self, loc_id, domain):
        return SQLLocation.objects.filter(location_type__in=['Regional Medical Store', 'Central Medical Store'],
                                          domain=domain)


class EmailReportingData(EWSData):
    title = "Reporting"
    slug = "reporting"
    show_table = True

    def get_locations(self, loc_id, domain):
        return []

    @property
    def headers(self):
        return DataTablesHeader(*[
            DataTablesColumn(_('% of facilities are reporting')),
            DataTablesColumn(_('% of submitted reports are complete')),
        ])

    @property
    def rows(self):
        def percent(x, y):
            return "%d%% (%d/%d)" % (x * 100 / (y or 1), x, y)

        locations = self.get_locations(self.config['location_id'], self.config['domain'])
        reported = StockTransaction.objects.filter(
            case_id__in=locations, report__date__range=[self.config['startdate'],
                                                        self.config['enddate']]).distinct('case_id').count()
        completed = 0
        all_products_count = SQLProduct.objects.filter(domain=self.config['domain'], is_archived=False).count()
        for loc in locations:
            products_count = SQLLocation.objects.get(supply_point_id=loc)._products.count()
            products_count = products_count if products_count else all_products_count
            st = StockTransaction.objects.filter(
                case_id=loc, report__date__range=[self.config['startdate'],
                                                  self.config['enddate']]).distinct('product_id').count()
            if products_count == st:
                completed += 1

        return [[percent(reported, len(locations)), percent(completed, reported)]]


class StockSummaryReportingData(EmailReportingData):
    def get_locations(self, loc_id, domain):
        return [loc.supply_point_id for loc in get_supply_points(loc_id, domain)]


class CMSRMSSummaryReportingData(EmailReportingData):
    def get_locations(self, loc_id, domain):
        return [loc.supply_point_id for loc in
                SQLLocation.objects.filter(location_type__in=['Regional Medical Store', 'Central Medical Store'],
                                           domain=domain)]


class StockSummaryReport(MultiReport):
    title = "Weekly Stock Summary Report"
    fields = [AsyncLocationFilter, DatespanFilter]
    name = "Stock Summary Report"
    slug = 'stock_summary_report'
    exportable = False
    is_exportable = False
    split = False

    @property
    def report_config(self):
        return dict(
            domain=self.domain,
            startdate=self.datespan.startdate_utc,
            enddate=self.datespan.enddate_utc,
            location_id=self.request.GET.get('location_id'),
            program='',
            products=''
        )

    @property
    @memoized
    def data_providers(self):
        return [StockSummaryReportingData(self.report_config),
                StockSummaryReportData(self.report_config)]

    @classmethod
    def show_in_navigation(cls, domain=None, project=None, user=None):
        return True


class CMSRMSReport(MultiReport):
    title = "Weekly Stock Summary Report - CMS and RMS"
    fields = [DatespanFilter]
    name = "CMS and RMS Summary Report"
    slug = 'cms_rms_summary_report'
    exportable = True
    is_exportable = True
    split = False

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
