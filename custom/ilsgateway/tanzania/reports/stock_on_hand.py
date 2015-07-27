from casexml.apps.stock.models import StockTransaction
from datetime import timedelta, datetime, time
from django.db.models import Q
from django.template.defaultfilters import floatformat
from corehq.apps.commtrack.models import SQLProduct, StockState
from corehq.apps.locations.models import SQLLocation
from corehq.apps.reports.datatables import DataTablesHeader, DataTablesColumn
from corehq.apps.reports.filters.fixtures import AsyncLocationFilter
from django.utils import html
from custom.ilsgateway.filters import ProgramFilter, ILSDateFilter
from custom.ilsgateway.models import SupplyPointStatusTypes, ProductAvailabilityData, \
    OrganizationSummary, SupplyPointStatus, SupplyPointStatusValues
from custom.ilsgateway.tanzania import ILSData, DetailsReport
from custom.ilsgateway.tanzania.reports.facility_details import FacilityDetailsReport, InventoryHistoryData, \
    RegistrationData, RandRHistory, RecentMessages, Notes
from custom.ilsgateway.tanzania.reports.mixins import ProductAvailabilitySummary, SohSubmissionData
from django.utils.translation import ugettext as _
from custom.ilsgateway.tanzania.reports.utils import link_format, format_percent, make_url
from dimagi.utils.dates import get_business_day_of_month, get_day_of_month
from dimagi.utils.decorators.memoized import memoized
from django.db.models.aggregates import Avg, Max


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

    @property
    def rows(self):
        rows = []
        if not self.config['products']:
            prd_id = SQLProduct.objects.filter(
                domain=self.config['domain']
            ).order_by('code').values_list('product_id', flat=True)
        else:
            prd_id = self.config['products']

        if self.config['location_id']:
            locations = SQLLocation.objects.filter(parent__location_id=self.config['location_id'])
            for loc in locations:
                org_summary = OrganizationSummary.objects.filter(
                    date__range=(self.config['startdate'], self.config['enddate']),
                    location_id=loc.location_id
                )
                self.config['org_summary'] = org_summary

                soh_rows = SohSubmissionData(config=self.config).rows
                soh_data = soh_rows[0] if soh_rows else None
                facs = get_facilities(loc, self.config['domain'])
                facs_count = facs.count()

                if soh_data and facs_count > 0:
                    soh_on_time = soh_data.on_time * 100 / facs_count
                    soh_late = soh_data.late * 100 / facs_count
                    soh_not_responding = soh_data.not_responding * 100 / facs_count
                else:
                    soh_on_time = None
                    soh_late = None
                    soh_not_responding = None

                if facs_count > 0:
                    fac_ids = facs.exclude(supply_point_id__isnull=True).values_list('supply_point_id', flat=True)
                    enddate = self.config['enddate']
                    month = enddate.month - 1 if enddate.month != 1 else 12
                    year = enddate.year - 1 if enddate.month == 1 else enddate.year
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
                else:
                    percent_stockouts = 0

                url = make_url(StockOnHandReport, self.config['domain'],
                               '?location_id=%s&filter_by_program=%s&'
                               'datespan_type=%s&datespan_first=%s&datespan_second=%s',
                               (loc.location_id,
                                self.config['program'], self.config['datespan_type'],
                                self.config['datespan_first'], self.config['datespan_second']))

                row_data = [
                    link_format(loc.name, url),
                    format_percent(soh_on_time),
                    format_percent(soh_late),
                    format_percent(soh_not_responding),
                    format_percent(percent_stockouts)
                ]
                for product in prd_id:
                    ps = ProductAvailabilityData.objects.filter(
                        location_id=loc.location_id,
                        product=product,
                        date__range=(self.config['startdate'], self.config['enddate'])
                    ).aggregate(without_stock=Avg('without_stock'), total=Max('total'))
                    if ps['without_stock'] and ps['total']:
                        row_data.append(format_percent(ps['without_stock'] * 100 / float(ps['total'])))
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

    @property
    def headers(self):
        if self.config['products']:
            products = SQLProduct.objects.filter(product_id__in=self.config['products'],
                                                 domain=self.config['domain']).order_by('code')
        else:
            products = SQLProduct.objects.filter(domain=self.config['domain']).order_by('code')
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

        def get_last_reported(supplypoint):

            last_bd_of_the_month = get_business_day_of_month(enddate.year,
                                                             enddate.month,
                                                             -1)
            st = StockTransaction.objects.filter(
                case_id=supplypoint,
                type='stockonhand',
                report__date__lte=last_bd_of_the_month,
                report__domain=self.config['domain']
            ).order_by('-report__date')
            last_of_last_month = datetime(enddate.year, enddate.month, 1) - timedelta(days=1)
            last_bd_of_last_month = datetime.combine(get_business_day_of_month(last_of_last_month.year,
                                                     last_of_last_month.month,
                                                     -1), time())
            if st:
                sts = _reported_on_time(last_bd_of_last_month, st[0].report.date)
                return sts, st[0].report.date.date()
            else:
                sts = OnTimeStates.NO_DATA
                return sts, None

        def get_hisp_resp_rate(location):
            statuses = SupplyPointStatus.objects.filter(
                location_id=location.location_id,
                status_type=SupplyPointStatusTypes.SOH_FACILITY
            )
            if not statuses:
                return None
            status_month_years = set([(x.status_date.month, x.status_date.year) for x in statuses])
            denom = len(status_month_years)
            num = 0
            for s in status_month_years:
                f = statuses.filter(status_date__month=s[0], status_date__year=s[1]).filter(
                    Q(status_value=SupplyPointStatusValues.SUBMITTED) |
                    Q(status_value=SupplyPointStatusValues.NOT_SUBMITTED) |
                    Q(status_value=SupplyPointStatusValues.RECEIVED) |
                    Q(status_value=SupplyPointStatusValues.NOT_RECEIVED)
                ).order_by("-status_date")
                if f.count():
                    num += 1

            return float(num) / float(denom), num, denom

        if not self.config['products']:
            products = SQLProduct.objects.filter(domain=self.config['domain'], is_archived=False).order_by('code')
        else:
            products = SQLProduct.objects.filter(product_id__in=self.config['products'],
                                                 domain=self.config['domain']).order_by('code')

        if self.config['location_id']:
            locations = SQLLocation.objects.filter(parent__location_id=self.config['location_id'])
            for loc in locations:
                supply_point = loc.supply_point_id

                status, last_reported = get_last_reported(supply_point)
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
                        def calculate_months_remaining(stock_state, quantity):
                            consumption = stock_state.daily_consumption
                            if consumption is not None and consumption > 0 and quantity is not None:
                                return float(quantity) / float(30 * consumption)
                            elif quantity == 0:
                                return 0
                            return None
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
