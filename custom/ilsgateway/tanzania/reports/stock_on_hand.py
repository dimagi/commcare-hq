from collections import defaultdict
from casexml.apps.stock.models import StockTransaction
from datetime import timedelta, datetime
from django.template.defaultfilters import floatformat
from corehq.apps.commtrack.models import SQLProduct, StockState
from corehq.apps.locations.models import SQLLocation
from corehq.apps.reports.datatables import DataTablesHeader, DataTablesColumn
from corehq.apps.reports.filters.fixtures import AsyncLocationFilter
from django.utils import html
from custom.ilsgateway.filters import ProgramFilter, ILSDateFilter
from custom.ilsgateway.models import ProductAvailabilityData, \
    OrganizationSummary
from custom.ilsgateway.tanzania.reports.facility_details import FacilityDetailsReport, InventoryHistoryData, \
    RegistrationData, RandRHistory, RecentMessages, Notes
from custom.ilsgateway.tanzania.reports.mixins import ProductAvailabilitySummary, SohSubmissionData
from django.utils.translation import ugettext as _
from custom.ilsgateway.tanzania.reports.utils import link_format, format_percent, make_url, get_hisp_resp_rate, \
    get_last_reported, calculate_months_remaining
from dimagi.utils.dates import get_day_of_month
from dimagi.utils.decorators.memoized import memoized
from django.db.models.aggregates import Avg, Max
from custom.ilsgateway.tanzania import ILSData, DetailsReport


def get_facilities(location, domain):

    if location.location_type.name.upper() == 'DISTRICT':
        locations = SQLLocation.objects.filter(parent=location, is_archived=False)
    elif location.location_type.name.upper() == 'REGION':
        locations = SQLLocation.objects.filter(parent__parent=location, is_archived=False)
    elif location.location_type.name.upper() == 'MSDZONE':
        locations = SQLLocation.objects.filter(parent__parent__parent=location, is_archived=False)
    elif location.location_type.name.upper() == 'FACILITY':
        locations = SQLLocation.objects.filter(id=location.id, is_archived=False)
    else:
        locations = SQLLocation.objects.filter(domain=domain, is_archived=False)
    return locations

def product_format(ret, srs, month):
    NO_DATA = -1
    STOCKOUT = 0.00
    LOW = 3
    ADEQUATE = 6

    mos = float(ret)
    text = '%s'
    if mos == NO_DATA:
        text = '<span style="color:grey">%s</span>'
    elif mos == STOCKOUT:
        text = '<span class="icon-remove" style="color:red"/>%s'
    elif mos < LOW:
        text = '<span class="icon-warning-sign" style="color:orange"/>%s'
    elif mos <= ADEQUATE:
        text = '<span class="icon-ok" style="color:green"/>%s'
    elif mos > ADEQUATE:
        text = '<span class="icon-arrow-up" style="color:purple"/>%s'

    if month:
        if srs:
            return text % ('%.2f' % mos)
        return text % 'No Data'
    else:
        if srs:
            return text % ('%.0f' % srs.stock_on_hand)
        return text % 'No Data'


class SohPercentageTableData(ILSData):
    title = 'Inventory'
    slug = 'inventory_region_table'
    show_chart = False
    show_table = True
    searchable = True

    @property
    def headers(self):
        if self.config['products']:
            products = SQLProduct.objects.filter(product_id__in=self.config['products'],
                                                 domain=self.config['domain']).order_by('code')
        else:
            products = SQLProduct.objects.filter(domain=self.config['domain']).order_by('code')
        headers = DataTablesHeader(*[
            DataTablesColumn(_('Name')),
            DataTablesColumn(_('% Facilities Submitting Soh On Time')),
            DataTablesColumn(_('% Facilities Submitting Soh Late')),
            DataTablesColumn(_('% Facilities Not Responding To Soh')),
            DataTablesColumn(_('% Facilities With 1 Or More Stockouts This Month')),
        ])

        datespan_type = self.config['datespan_type']
        if datespan_type == 2:
            month = 'quarter'
        elif datespan_type == 3:
            month = 'year'
        else:
            month = 'month'

        for p in products:
            headers.add_column(DataTablesColumn(_('%s stock outs this %s') % (p.code, month)))

        return headers

    def get_soh_data(self, location, facs_count):
        org_summary = OrganizationSummary.objects.filter(
            date__range=(self.config['startdate'], self.config['enddate']),
            location_id=location.location_id
        )
        if facs_count > 0:
            soh_rows = SohSubmissionData(config={'org_summary': org_summary}).rows
            soh_data = soh_rows[0] if soh_rows else None
            if soh_data:
                soh_on_time = soh_data.on_time * 100 / facs_count
                soh_late = soh_data.late * 100 / facs_count
                soh_not_responding = soh_data.not_responding * 100 / facs_count
                return soh_late, soh_not_responding, soh_on_time
        return None, None, None

    def get_previous_month(self, enddate):
        month = enddate.month - 1 if enddate.month != 1 else 12
        year = enddate.year - 1 if enddate.month == 1 else enddate.year
        return month, year

    def get_stockouts(self, facs):
        facs_count = facs.count()
        if facs_count == 0:
            return 0

        fac_ids = facs.exclude(supply_point_id__isnull=True).values_list('supply_point_id', flat=True)
        enddate = self.config['enddate']
        month, year = self.get_previous_month(enddate)
        stockouts = StockTransaction.objects.filter(
            case_id__in=list(fac_ids),
            stock_on_hand__lte=0,
            report__domain=self.config['domain'],
            report__date__range=[
                datetime(year, month, 1),
                datetime(enddate.year, enddate.month, 1)
            ]
        ).order_by('case_id').distinct('case_id').count()
        percent_stockouts = (stockouts or 0) * 100 / float(facs_count)

        return percent_stockouts

    def get_products_ids(self):
        if not self.config['products']:
            products_ids = SQLProduct.objects.filter(
                domain=self.config['domain']
            ).order_by('code').values_list('product_id', flat=True)
        else:
            products_ids = self.config['products']
        return products_ids

    def _format_row(self, percent_stockouts, soh_late, soh_not_responding, soh_on_time, sql_location):
        url = make_url(
            StockOnHandReport,
            self.config['domain'],
            '?location_id=%s&filter_by_program=%s&'
            'datespan_type=%s&datespan_first=%s&datespan_second=%s',
            (sql_location.location_id, self.config['program'], self.config['datespan_type'],
             self.config['datespan_first'], self.config['datespan_second'])
        )
        row_data = [
            link_format(sql_location.name, url),
            format_percent(soh_on_time),
            format_percent(soh_late),
            format_percent(soh_not_responding),
            format_percent(percent_stockouts)
        ]
        return row_data

    def get_stockouts_map(self, enddate, location):
        month, year = self.get_previous_month(enddate)
        transactions = StockTransaction.objects.filter(
            stock_on_hand__lte=0,
            report__domain=self.config['domain'],
            report__date__range=[
                datetime(year, month, 1),
                datetime(enddate.year, enddate.month, 1)
            ]
        ).order_by('case_id').distinct('case_id')
        location_parent_dict = dict(
            location.get_descendants().filter(
                location_type__administrative=False
            ).values_list('supply_point_id', 'parent__parent__parent__location_id')
        )
        stockouts_map = defaultdict(lambda: 0)
        for transaction in transactions:
            stockouts_map[location_parent_dict[transaction.case_id]] += 1
        return stockouts_map

    @property
    def rows(self):
        rows = []
        products_ids = self.get_products_ids()

        if not self.config['location_id']:
            return rows

        location = SQLLocation.objects.get(location_id=self.config['location_id'])
        sql_locations = SQLLocation.objects.filter(parent__location_id=self.config['location_id'])
        is_mohsw = False
        stockouts_map = {}
        product_availabilities = {
            (pa['location_id'], pa['product']): (pa['without_stock'], pa['total'])
            for pa in ProductAvailabilityData.objects.filter(
                location_id__in=list(sql_locations.values_list('location_id', flat=True)),
                date__range=(self.config['startdate'], self.config['enddate'])
            ).values('location_id', 'product').annotate(without_stock=Avg('without_stock'), total=Max('total'))
        }
        if location.location_type.name == 'MOHSW':
            is_mohsw = True
            stockouts_map = self.get_stockouts_map(self.config['enddate'], location)

        for sql_location in sql_locations.exclude(is_archived=True):
            facilities = get_facilities(sql_location, self.config['domain'])
            facilities_count = facilities.count()

            soh_late, soh_not_responding, soh_on_time = self.get_soh_data(sql_location, facilities_count)
            if not is_mohsw:
                percent_stockouts = self.get_stockouts(facilities)
            else:
                if facilities_count > 0:
                    stockouts = stockouts_map.get(sql_location.location_id, 0)
                    percent_stockouts = stockouts * 100 / float(facilities_count)
                else:
                    percent_stockouts = 0

            row_data = self._format_row(
                percent_stockouts, soh_late, soh_not_responding, soh_on_time, sql_location
            )
            for product_id in products_ids:
                product_availability = product_availabilities.get((sql_location.location_id, product_id))
                if product_availability and product_availability[1] != 0:
                    row_data.append(
                        format_percent(
                            product_availability[0] * 100 / float(product_availability[1])
                        )
                    )
                else:
                    row_data.append("<span class='no_data'>No Data</span>")
            rows.append(row_data)
        return rows


class OnTimeStates(object):
    ON_TIME = "on time"
    LATE = "late"
    NO_DATA = "no data"
    INSUFFICIENT_DATA = "insufficient data"


def _reported_on_time(reminder_date, last_report_date):
    cutoff_date = reminder_date + timedelta(days=5)
    if last_report_date < reminder_date:
        return OnTimeStates.INSUFFICIENT_DATA
    elif last_report_date < cutoff_date:
        return OnTimeStates.ON_TIME
    else:
        return OnTimeStates.LATE


def icon_format(status, val):
    if status == OnTimeStates.ON_TIME:
        return '<span class="icon-ok" style="color:green"/>%s' % val
    elif status == OnTimeStates.LATE:
        return '<span class="icon-warning-sign" style="color:orange"/>%s' % val
    elif status == OnTimeStates.NO_DATA or OnTimeStates.INSUFFICIENT_DATA:
        return _('Waiting for reply')


def _months_or_default(val, default_value):
    try:
        return "%0.2f" % val
    except TypeError:
        return default_value


class DistrictSohPercentageTableData(ILSData):
    slug = 'inventory_district_table'
    show_chart = False
    show_table = True
    searchable = True

    @property
    def title(self):
        if self.config['soh_month']:
            return 'Month of Stock'
        return 'Inventory'

    @property
    def title_url(self):
        soh_month = True
        if self.config['soh_month']:
            soh_month = False
        return html.escape(make_url(StockOnHandReport, self.config['domain'],
                           '?location_id=%s&filter_by_program=%s&'
                           'datespan_type=%s&datespan_first=%s&datespan_second=%s&soh_month=%s',
                           (self.config['location_id'],
                            self.config['program'], self.config['datespan_type'],
                            self.config['datespan_first'], self.config['datespan_second'], soh_month)))

    @property
    def title_url_name(self):
        if self.config['soh_month']:
            return 'Inventory'
        return 'Month of Stock'

    @memoized
    def get_products(self):
        if self.config['products']:
            return SQLProduct.objects.filter(product_id__in=self.config['products'],
                                             domain=self.config['domain']).order_by('code')
        else:
            return SQLProduct.objects.filter(domain=self.config['domain']).order_by('code')

    @property
    def headers(self):
        products = self.get_products()
        headers = DataTablesHeader(
            DataTablesColumn(_('MSD Code')),
            DataTablesColumn(_('Facility Name')),
            DataTablesColumn(_('DG')),
            DataTablesColumn(_('Last Reported')),
            DataTablesColumn(_('Hist. Resp. Rate')),
        )

        for p in products:
            headers.add_column(DataTablesColumn(_(p.code)))

        return headers

    @property
    def rows(self):
        rows = []
        enddate = self.config['enddate']

        products = self.get_products()

        if self.config['location_id']:
            locations = SQLLocation.objects.filter(parent__location_id=self.config['location_id'])
            for loc in locations:
                supply_point = loc.supply_point_id

                status, last_reported = get_last_reported(supply_point, self.config['domain'], enddate)
                hisp = get_hisp_resp_rate(loc)

                url = make_url(FacilityDetailsReport, self.config['domain'],
                               '?location_id=%s&filter_by_program=%s&'
                               'datespan_type=%s&datespan_first=%s&datespan_second=%s',
                               (loc.location_id,
                                self.config['program'], self.config['datespan_type'],
                                self.config['datespan_first'], self.config['datespan_second']))

                row_data = [
                    loc.site_code,
                    link_format(loc.name, url),
                    loc.metadata.get('group', None),
                    icon_format(status, last_reported),
                    "<span title='%d of %d'>%s%%</span>" % (hisp[1],
                                                            hisp[2],
                                                            floatformat(hisp[0] * 100.0)) if hisp else "No data"
                ]

                for product in products:
                    last_of_the_month = get_day_of_month(enddate.year, enddate.month, -1)
                    first_of_the_next_month = last_of_the_month + timedelta(days=1)
                    try:
                        srs = StockTransaction.objects.filter(
                            report__domain=self.config['domain'],
                            report__date__lt=first_of_the_next_month,
                            case_id=supply_point,
                            product_id=product.product_id
                        ).order_by("-report__date")[0]
                    except IndexError:
                        srs = None

                    if srs:
                        try:
                            ss = StockState.objects.get(case_id=supply_point, product_id=product.product_id)
                            val = calculate_months_remaining(ss, srs.stock_on_hand)
                            ret = _months_or_default(val, -1)
                        except StockState.DoesNotExist:
                            ret = -1
                    else:
                        ret = -1

                    row_data.append(product_format(ret, srs, self.config['soh_month']))

                rows.append(row_data)

        return rows


class ProductSelectionPane(ILSData):
    slug = 'product_selection_pane'
    show_table = True
    show_chart = False
    title = 'Select Products'

    @property
    def rows(self):
        products = SQLProduct.objects.filter(product_id__in=self.config['products'],
                                             is_archived=False).order_by('code')
        result = [
            [
                '<input class=\"toggle-column\" data-column={2} value=\"{0}\" type=\"checkbox\"'
                '{3}>{1} ({0})</input>'
                .format(p.code, p.name, idx, 'checked' if 5 <= idx <= 14 else 'disabled')
            ] for idx, p in enumerate(products, start=5)
        ]
        return result


class StockOnHandReport(DetailsReport):
    slug = "stock_on_hand"
    name = 'Stock On Hand'
    use_datatables = True

    @property
    def title(self):
        title = _('Stock On Hand {0}'.format(self.title_month))
        if self.location and self.location.location_type.name.upper() == 'FACILITY':
            return "{0} ({1}) Group {2}".format(self.location.name,
                                                self.location.site_code,
                                                self.location.metadata.get('group', '---'))
        return title

    @property
    def fields(self):
        fields = [AsyncLocationFilter, ILSDateFilter, ProgramFilter]
        if self.location and self.location.location_type.name.upper() == 'FACILITY':
            fields = []
        return fields

    @property
    @memoized
    def data_providers(self):
        config = self.report_config
        data_providers = []
        if config['org_summary']:
            location = SQLLocation.objects.get(location_id=config['org_summary'][0].location_id)

            data_providers = [
                SohSubmissionData(config=config, css_class='row_chart'),
                ProductSelectionPane(config=config, css_class='row_chart'),
                ProductAvailabilitySummary(config=config, css_class='row_chart_all', chart_stacked=False),
            ]

            if location.location_type.name.upper() == 'DISTRICT':
                data_providers.append(DistrictSohPercentageTableData(config=config, css_class='row_chart_all'))
            elif location.location_type.name.upper() == 'FACILITY':
                return [
                    InventoryHistoryData(config=config),
                    RandRHistory(config=config),
                    Notes(config=config),
                    RecentMessages(config=config),
                    RegistrationData(config=dict(loc_type='FACILITY', **config), css_class='row_chart_all'),
                    RegistrationData(config=dict(loc_type='DISTRICT', **config), css_class='row_chart_all'),
                    RegistrationData(config=dict(loc_type='REGION', **config), css_class='row_chart_all')
                ]
            else:
                data_providers.append(SohPercentageTableData(config=config, css_class='row_chart_all'))
        return data_providers

    @property
    def report_context(self):
        ret = super(StockOnHandReport, self).report_context
        ret['view_mode'] = 'stockonhand'
        return ret
