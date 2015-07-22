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
from dimagi.utils.decorators.memoized import memoized


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

    @property
    def rows(self):
        def percent(x, y):
            return "%d%% <small>(%d)</small>" % (x * 100 / (y or 1), x)

        def _stock_status(status, loc):
            daily = status.daily_consumption or 0
            state = status.stock_on_hand / ((daily * 30) or 1)
            if state == 0.0:
                return "stockout"
            elif state < loc.location_type.understock_threshold:
                return "adequate"
            elif state < loc.location_type.overstock_threshold + 7:
                return "low"
            else:
                return "overstock"

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
                if location.products.filter(code=state.sql_product.code):
                    row_data[p_name]['total_fac'] += 1
                row_data[p_name]['reported_fac'] += 1
                s = _stock_status(state, location)
                row_data[p_name][s] += 1

        rows = []
        for k, v in row_data.iteritems():
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
            stock_states = StockState.objects.filter(
                case_id=location.supply_point_id,
                section_id=STOCK_SECTION_TYPE,
                sql_product__in=products
            )

            for state in stock_states:
                p_name = state.sql_product.name
                if location.products.filter(code=state.sql_product.code):
                    row_data[p_name]['total_fac'] += 1
                row_data[p_name]['reported_fac'] += 1
                if not state.stock_on_hand:
                    row_data[p_name]['fac_with_stockout'] += 1
                row_data[p_name][location.pk] = int(state.stock_on_hand)
                row_data[p_name]['total'] += int(state.stock_on_hand)

        rows = []
        for k, v in row_data.iteritems():
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
    def title(self):
        return 'Weekly Stock Summary Report - {0} - {1} {2}'.format(
            SQLLocation.objects.get(location_id=self.report_config['location_id']).name,
            ews_date_format(self.datespan.startdate_utc),
            ews_date_format(self.datespan.enddate_utc)
        )

    @property
    def report_config(self):
        location_id = self.request.GET.get('location_id')
        return dict(
            domain=self.domain,
            startdate=self.datespan.startdate_utc,
            enddate=self.datespan.enddate_utc,
            location_id=location_id if location_id else get_country_id(self.domain),
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
