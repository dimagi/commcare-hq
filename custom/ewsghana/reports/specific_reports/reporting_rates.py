from datetime import datetime
from corehq import Domain
from corehq.apps.locations.models import SQLLocation
from corehq.apps.reports.datatables import DataTablesHeader, DataTablesColumn
from corehq.apps.reports.filters.fixtures import AsyncLocationFilter
from corehq.apps.reports.graph_models import PieChart
from custom.ewsghana import StockLevelsReport
from custom.ewsghana.reports import MultiReport, EWSData
from casexml.apps.stock.models import StockTransaction
from custom.ewsghana.reports.stock_levels_report import FacilityReportData, StockLevelsLegend, FacilitySMSUsers, \
    FacilityUsers, FacilityInChargeUsers, InventoryManagementData, InputStock
from custom.ewsghana.utils import calculate_last_period, get_supply_points
from corehq.apps.reports.filters.dates import DatespanFilter
from custom.ilsgateway.tanzania import make_url
from custom.ilsgateway.tanzania.reports.utils import link_format
from django.utils.translation import ugettext as _
from dimagi.utils.dates import DateSpan


# TODO Implement this when alerts (moving from EWS) will be finished
class AlertsData(EWSData):
    pass


class ReportingRates(EWSData):
    show_table = False
    show_chart = True
    slug = 'reporting_rates'
    title = _('Reporting Rates')

    @property
    def rows(self):
        rows = {}
        if self.config['location_id']:
            supply_points = get_supply_points(self.config['location_id'], self.config['domain']).values_list(
                'supply_point_id', flat=True
            )
            last_period_st, last_period_end = calculate_last_period(self.config['enddate'])
            reports = StockTransaction.objects.filter(case_id__in=supply_points,
                                                      report__date__range=[last_period_st,
                                                                           last_period_end]
                                                      ).distinct('case_id').count()
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
                     label=_('Reported'),
                     description=_("%.2f%% (%d) Reported (last 7 days)" % (reported_percent, data['total'])),
                     color='green'),
                dict(value=non_reported_percent,
                     label=_('Non-Reported'),
                     description=_("%.2f%% (%d) Non-Reported (last 7 days)" %
                                   (non_reported_percent, data['total'])),
                     color='red'),
            ]

        return [PieChart('', '', chart_data, ['green', 'red'])]


class ReportingDetails(EWSData):
    show_table = False
    show_chart = True
    slug = 'reporting_details'
    title = _('Reporting Details')

    @property
    def rows(self):
        rows = {}
        if self.config['location_id']:
            last_period_st, last_period_end = calculate_last_period(self.config['enddate'])
            supply_points = get_supply_points(self.config['location_id'], self.config['domain']).values_list(
                'supply_point_id', flat=True
            )
            complete = 0
            incomplete = 0
            for sp in supply_points:
                products_count = len(SQLLocation.objects.get(supply_point_id=sp).products)
                st = StockTransaction.objects.filter(case_id=sp,
                                                     report__date__range=[last_period_st,
                                                                          last_period_end]
                                                     ).distinct('product_id').count()
                if products_count == st:
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
                     label=_('Completed'),
                     description=_("%.2f%% (%d) Complete Reports in last 7 days" %
                                   (complete_percent, data['total'])),
                     color='green'),
                dict(value=incomplete_percent,
                     label=_('Incompleted'),
                     description=_("%.2f%% (%d) Incomplete Reports in last 7 days" %
                                   (incomplete_percent, data['total'])),
                     color='purple'),
            ]

        return [PieChart('', '', chart_data, ['green', 'purple'])]


class SummaryReportingRates(EWSData):

    show_table = True
    show_chart = False
    slug = 'summary_reporting'
    title = _('Summary Reporting Rates')
    use_datatables = True

    @property
    def get_locations(self):
        location_types = [
            loc_type.name for loc_type in filter(lambda loc_type: loc_type.administrative,
                                                 Domain.get_by_name(self.config['domain']).location_types
                                                 )
        ]
        return SQLLocation.objects.filter(parent__location_id=self.config['location_id'],
                                          location_type__in=location_types)

    @property
    def headers(self):
        if self.config['location_id']:

            return DataTablesHeader(*[
                DataTablesColumn(_(self.get_locations[0].location_type.title())),
                DataTablesColumn(_('# Sites')),
                DataTablesColumn(_('# Reporting')),
                DataTablesColumn(_('Reporting Rate'))
            ])
        else:
            return []

    @property
    def rows(self):
        rows = []
        if self.config['location_id']:
            last_period_st, last_period_end = calculate_last_period(self.config['enddate'])
            for loc in self.get_locations:
                supply_points = get_supply_points(loc.location_id, loc.domain).values_list('supply_point_id',
                                                                                           flat=True)
                sites = len(supply_points)

                reported = StockTransaction.objects.filter(case_id__in=supply_points,
                                                           report__date__range=[last_period_st,
                                                                                last_period_end]
                                                           ).distinct('case_id').count()
                reporting_rates = '%.2f%%' % (reported * 100 / (float(sites) or 1.0))

                url = make_url(
                    ReportingRatesReport,
                    self.config['domain'],
                    '?location_id=%s&startdate=%s&enddate=%s',
                    (loc.location_id, self.config['startdate'], self.config['enddate']))

                rows.append([link_format(loc.name, url), sites, reported, reporting_rates])
        return rows


class NonReporting(EWSData):
    show_table = True
    show_chart = False
    slug = 'non_reporting'
    use_datatables = True

    @property
    def title(self):
        if self.config['location_id']:
            ltype = SQLLocation.objects.get(location_id=self.config['location_id']).location_type.lower()
            if ltype == 'country':
                return _('Non Reporting RMS and THs')
            else:
                return _('Non Reporting Facilities')
        return ''

    @property
    def headers(self):
        if self.config['location_id']:

            return DataTablesHeader(*[
                DataTablesColumn(_('Name')),
                DataTablesColumn(_('Last Stock Report Received')),
            ])
        else:
            return []

    @property
    def rows(self):
        rows = []
        if self.config['location_id']:
            supply_points = get_supply_points(self.config['location_id'], self.config['domain']).values_list(
                'supply_point_id', flat=True
            )
            last_period_st, last_period_end = calculate_last_period(self.config['enddate'])
            reported = StockTransaction.objects.filter(case_id__in=supply_points,
                                                       report__date__range=[last_period_st,
                                                                            last_period_end]
                                                       ).values_list('case_id', flat=True)

            not_reported = SQLLocation.objects.filter(location_type__in=self.location_types,
                                                      parent__location_id=self.config['location_id'])\
                .exclude(supply_point_id__in=reported)

            for loc in not_reported:
                url = make_url(
                    StockLevelsReport,
                    self.config['domain'],
                    '?location_id=%s&startdate=%s&enddate=%s',
                    (loc.location_id, self.config['startdate'], self.config['enddate']))

                st = StockTransaction.objects.filter(case_id=loc.supply_point_id).order_by('-report__date')
                if st:
                    date = st[0].report.date
                else:
                    date = _('---')
                rows.append([link_format(loc.name, url), date])
        return rows


class InCompleteReports(EWSData):

    show_table = True
    show_chart = False
    slug = 'incomplete_reporting'
    title = _('Incomplete Reports')
    use_datatables = True

    @property
    def headers(self):
        if self.config['location_id']:

            return DataTablesHeader(*[
                DataTablesColumn(_('Name')),
                DataTablesColumn(_('Last Stock Report Received')),
            ])
        else:
            return []

    @property
    def rows(self):
        rows = []
        if self.config['location_id']:
            last_period_st, last_period_end = calculate_last_period(self.config['enddate'])
            locations = SQLLocation.objects.filter(parent__location_id=self.config['location_id'],
                                                   location_type__in=self.location_types)
            for loc in locations:
                st = StockTransaction.objects.filter(case_id=loc.supply_point_id,
                                                     report__date__range=[last_period_st,
                                                                          last_period_end]
                                                     ).order_by('-report__date')
                st_count = st.distinct('product_id').count()
                if len(loc.products) != st_count:
                    if st:
                        date = st[0].report.date
                    else:
                        date = '---'

                    url = make_url(
                        StockLevelsReport,
                        self.config['domain'],
                        '?location_id=%s&startdate=%s&enddate=%s',
                        (loc.location_id, self.config['startdate'], self.config['enddate']))
                    rows.append([link_format(loc.name, url), date])
        return rows


class ReportingRatesReport(MultiReport):

    name = 'Reporting Page'
    title = 'Reporting Page'
    slug = 'reporting_page'
    fields = [AsyncLocationFilter, DatespanFilter]
    split = False

    @property
    def report_config(self):
        return dict(
            domain=self.domain,
            startdate=self.datespan.startdate_utc,
            enddate=self.datespan.enddate_utc,
            location_id=self.request.GET.get('location_id'),
            products=None,
            program=None
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
                InventoryManagementData(config)
            ]
        self.split = False
        data_providers = [
            ReportingRates(config=config),
            ReportingDetails(config=config)]

        if config['location_id']:
            location = SQLLocation.objects.get(location_id=config['location_id'])
            if location.location_type.lower() in ['country', 'region']:
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
