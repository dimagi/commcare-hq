from datetime import datetime, timedelta
from corehq import Domain
from corehq.apps.es import UserES
from corehq.apps.locations.models import SQLLocation
from corehq.apps.reports.datatables import DataTablesHeader, DataTablesColumn
from corehq.apps.reports.filters.fixtures import AsyncLocationFilter
from corehq.apps.reports.graph_models import PieChart
from custom.common import ALL_OPTION
from custom.ewsghana import StockLevelsReport
from custom.ewsghana.filters import ProductByProgramFilter
from custom.ewsghana.reports import MultiReport, ReportingRatesData, ProductSelectionPane
from casexml.apps.stock.models import StockTransaction
from custom.ewsghana.reports.stock_levels_report import FacilityReportData, StockLevelsLegend, FacilitySMSUsers, \
    FacilityUsers, FacilityInChargeUsers, InventoryManagementData, InputStock
from custom.ewsghana.utils import calculate_last_period, get_country_id
from corehq.apps.reports.filters.dates import DatespanFilter
from custom.ilsgateway.tanzania import make_url
from custom.ilsgateway.tanzania.reports.utils import link_format
from django.utils.translation import ugettext as _
from dimagi.utils.dates import DateSpan


class ReportingRates(ReportingRatesData):
    show_table = False
    show_chart = True
    slug = 'reporting_rates'
    title = _('Reporting Rates')

    @property
    def rows(self):
        rows = {}
        if self.location_id:
            if self.location.location_type.name == 'country':
                supply_points = self.all_reporting_locations()
                reports = len(self.reporting_supply_points(supply_points))
            else:
                supply_points = self.get_supply_points().values_list(
                    'supply_point_id', flat=True
                )
                reports = len(self.reporting_supply_points())
            rows = dict(
                total=len(supply_points),
                reported=reports,
                non_reported=len(supply_points) - reports
            )
        return rows

    @property
    def charts(self):
        data = self.rows
        chart_data = []
        if data:
            reported_percent = float(data['reported']) * 100 / (data['total'] or 1)
            non_reported_percent = float(data['non_reported']) * 100 / (data['total'] or 1)
            chart_data = [
                dict(value=reported_percent,
                     label=_('Reporting'),
                     description=_("%.2f%% (%d) Reported (last 7 days)" % (reported_percent, data['reported'])),
                     color='green'),
                dict(value=non_reported_percent,
                     label=_('Non-Reporting'),
                     description=_("%.2f%% (%d) Non-Reported (last 7 days)" %
                                   (non_reported_percent, data['non_reported'])),
                     color='red'),
            ]

        return [PieChart('', '', chart_data, ['green', 'red'])]


class ReportingDetails(ReportingRatesData):
    show_table = False
    show_chart = True
    slug = 'reporting_details'
    title = _('Reporting Details')

    @property
    def rows(self):
        rows = {}
        if self.location_id:
            last_period_st, last_period_end = calculate_last_period(self.config['enddate'])
            if self.location.location_type.name == 'country':
                supply_points = self.reporting_supply_points(self.all_reporting_locations())
            else:
                supply_points = self.reporting_supply_points()
            complete = 0
            incomplete = 0
            for supply_point in supply_points:
                products = {
                    product.product_id
                    for product in SQLLocation.objects.get(supply_point_id=supply_point).products
                }
                st = StockTransaction.objects.filter(
                    case_id=supply_point,
                    report__date__range=[last_period_st, last_period_end]
                ).distinct('product_id').values_list('product_id', flat=True)
                if not (products - set(st)):
                    complete += 1
                else:
                    incomplete += 1
            rows = dict(
                total=complete + incomplete,
                complete=complete,
                incomplete=incomplete
            )
        return rows

    @property
    def charts(self):
        data = self.rows
        chart_data = []
        if data:
            complete_percent = float(data['complete']) * 100 / (data['total'] or 1)
            incomplete_percent = float(data['incomplete']) * 100 / (data['total'] or 1)
            chart_data = [
                dict(value=complete_percent,
                     label=_('Complete'),
                     description=_("%.2f%% (%d) Complete Reports in last 7 days" %
                                   (complete_percent, data['complete'])),
                     color='green'),
                dict(value=incomplete_percent,
                     label=_('Incomplete'),
                     description=_("%.2f%% (%d) Incomplete Reports in last 7 days" %
                                   (incomplete_percent, data['incomplete'])),
                     color='purple'),
            ]

        return [PieChart('', '', chart_data, ['green', 'purple'])]


class SummaryReportingRates(ReportingRatesData):

    show_table = True
    show_chart = False
    slug = 'summary_reporting'
    title = _('Summary Reporting Rates')
    use_datatables = True

    @property
    def get_locations(self):
        location_types = [
            location_type.name
            for location_type in Domain.get_by_name(self.domain).location_types
            if location_type.administrative
        ]
        return SQLLocation.objects.filter(parent__location_id=self.config['location_id'],
                                          location_type__name__in=location_types, is_archived=False)

    @property
    def headers(self):
        if self.location_id:
            return DataTablesHeader(
                DataTablesColumn(_(self.get_locations[0].location_type.name.title())),
                DataTablesColumn(_('# Sites')),
                DataTablesColumn(_('# Reporting')),
                DataTablesColumn(_('Reporting Rate'))
            )
        else:
            return []

    @property
    def rows(self):
        rows = []
        if self.location_id:
            last_period_st, last_period_end = calculate_last_period(self.config['enddate'])
            for location in self.get_locations:
                supply_points = self.get_supply_points(location.location_id)
                sites = supply_points.count()
                reported = StockTransaction.objects.filter(
                    case_id__in=supply_points.values_list('supply_point_id', flat=True),
                    report__date__range=[last_period_st, last_period_end]
                ).distinct('case_id').count()
                reporting_rates = '%.2f%%' % (reported * 100 / (float(sites) or 1.0))

                url = make_url(
                    ReportingRatesReport,
                    self.config['domain'],
                    '?location_id=%s&startdate=%s&enddate=%s',
                    (location.location_id, self.config['startdate'], self.config['enddate']))

                rows.append([link_format(location.name, url), sites, reported, reporting_rates])
        return rows


class NonReporting(ReportingRatesData):
    show_table = True
    show_chart = False
    slug = 'non_reporting'
    use_datatables = True

    @property
    def title(self):
        if self.location_id:
            location_type = self.location.location_type.name.lower()
            if location_type == 'country':
                return _('Non Reporting RMS and THs')
            else:
                return _('Non Reporting Facilities')
        return ''

    @property
    def headers(self):
        if self.location_id:

            return DataTablesHeader(
                DataTablesColumn(_('Name')),
                DataTablesColumn(_('Last Stock Report Received')),
            )
        else:
            return []

    @property
    def rows(self):
        rows = []
        if self.location_id:
            supply_points = self.get_supply_points()
            not_reported = supply_points.exclude(supply_point_id__in=self.reporting_supply_points())

            for location in not_reported:
                url = make_url(
                    StockLevelsReport,
                    self.config['domain'],
                    '?location_id=%s&startdate=%s&enddate=%s',
                    (location.location_id, self.config['startdate'], self.config['enddate'])
                )

                st = StockTransaction.objects.filter(case_id=location.supply_point_id).order_by('-report__date')
                if st:
                    date = st[0].report.date.strftime("%m-%d-%Y")
                else:
                    date = '---'
                rows.append([link_format(location.name, url), date])
        return rows


class InCompleteReports(ReportingRatesData):

    show_table = True
    show_chart = False
    slug = 'incomplete_reporting'
    title = _('Incomplete Reports')
    use_datatables = True

    @property
    def headers(self):
        if self.location_id:
            return DataTablesHeader(
                DataTablesColumn(_('Name')),
                DataTablesColumn(_('Last Stock Report Received'))
            )
        else:
            return []

    @property
    def rows(self):
        rows = []
        if self.location_id:
            last_period_st, last_period_end = calculate_last_period(self.config['enddate'])
            locations = self.reporting_supply_points(self.all_reporting_locations())
            for location in SQLLocation.objects.filter(supply_point_id__in=locations):
                st = StockTransaction.objects.filter(
                    case_id=location.supply_point_id,
                    report__date__range=[last_period_st, last_period_end]
                ).order_by('-report__date')
                products_per_location = {product.product_id for product in location.products}
                if products_per_location - set(st.values_list('product_id', flat=True)):
                    if st:
                        date = st[0].report.date.strftime("%m-%d-%Y")
                    else:
                        date = '---'

                    url = make_url(
                        StockLevelsReport,
                        self.config['domain'],
                        '?location_id=%s&startdate=%s&enddate=%s',
                        (location.location_id, self.config['startdate'], self.config['enddate']))
                    rows.append([link_format(location.name, url), date])
        return rows


class AlertsData(ReportingRatesData):
    show_table = True
    show_chart = False
    slug = 'alerts'
    title = _('Alerts')

    @property
    def headers(self):
        return []

    def supply_points_reporting_last_month(self, supply_points):
        enddate = datetime.today()
        startdate = enddate - timedelta(days=30)
        result = StockTransaction.objects.filter(
            case_id__in=supply_points,
            report__date__range=[startdate, enddate]
        ).distinct('case_id').values_list('case_id', flat=True)
        return result

    def supply_points_users(self, supply_points):
        query = UserES().mobile_users().domain(self.config['domain']).term("domain_membership.location_id",
                                                                           [sp for sp in supply_points])
        with_reporters = set()
        with_in_charge = set()

        for hit in query.run().hits:
            with_reporters.add(hit['domain_membership']['location_id'])
            if hit['user_data'].get('role') == 'In Charge':
                with_in_charge.add(hit['domain_membership']['location_id'])

        return with_reporters, with_in_charge

    @property
    def rows(self):
        rows = []
        if self.location_id:
            supply_points = self.get_supply_points()
            reported = self.supply_points_reporting_last_month(supply_points.values_list('supply_point_id',
                                                                                         flat=True))
            with_reporters, with_in_charge = self.supply_points_users(supply_points.values_list('location_id',
                                                                                                flat=True))
            for sp in supply_points:
                url = make_url(
                    StockLevelsReport, self.config['domain'], '?location_id=%s&startdate=%s&enddate=%s',
                    (sp.location_id, self.config['startdate'].strftime("%Y-%m-%d"),
                     self.config['enddate'].strftime("%Y-%m-%d"))
                )
                if sp.supply_point_id not in reported:
                    rows.append(['<div style="background-color: rgba(255, 0, 0, 0.2)">%s has not reported last '
                                 'month. <a href="%s">[details]</a></div>' % (sp.name, url)])
                if sp.location_id not in with_reporters:
                    rows.append(['<div style="background-color: rgba(255, 0, 0, 0.2)">%s has not no reporters'
                                 ' registered. <a href="%s">[details]</a></div>' % (sp.name, url)])
                if sp.location_id not in with_in_charge:
                    rows.append(['<div style="background-color: rgba(255, 0, 0, 0.2)">%s has not no in-charge '
                                 'registered. <a href="%s">[details]</a></div>' % (sp.name, url)])

        if not rows:
            rows.append(['<div style="background-color: rgba(0, 255, 0, 0.2)">No current alerts</div>'])

        return rows


class ReportingRatesReport(MultiReport):

    name = 'Reporting Page'
    title = 'Reporting Page'
    slug = 'reporting_page'
    fields = [AsyncLocationFilter, ProductByProgramFilter, DatespanFilter]
    split = False

    def report_filters(self):
        return [f.slug for f in [AsyncLocationFilter, DatespanFilter]]

    @property
    def report_config(self):
        program = self.request.GET.get('filter_by_program')
        return dict(
            domain=self.domain,
            startdate=self.datespan.startdate_utc,
            enddate=self.datespan.enddate_utc,
            location_id=self.request.GET.get('location_id') or get_country_id(self.domain),
            products=None,
            program=program if program != ALL_OPTION else None,
        )

    @property
    def data_providers(self):
        config = self.report_config
        if self.is_reporting_type():
            self.split = True
            return [
                FacilityReportData(config),
                StockLevelsLegend(config),
                InputStock(config),
                FacilitySMSUsers(config),
                FacilityUsers(config),
                FacilityInChargeUsers(config),
                InventoryManagementData(config),
                ProductSelectionPane(config),
            ]
        self.split = False
        data_providers = [
            AlertsData(config=config),
            ReportingRates(config=config),
            ReportingDetails(config=config)]

        if config['location_id']:
            location = SQLLocation.objects.get(location_id=config['location_id'])
            if location.location_type.name.lower() in ['country', 'region']:
                data_providers.append(SummaryReportingRates(config=config))

        data_providers.extend([
            NonReporting(config=config),
            InCompleteReports(config=config)
        ])
        return data_providers

    @property
    def default_datespan(self):
        last_period_st, last_period_end = calculate_last_period(datetime.now())
        datespan = DateSpan(startdate=last_period_st, enddate=last_period_end)
        datespan.is_default = True
        return datespan
