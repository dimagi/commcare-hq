from corehq.apps.products.models import SQLProduct
from corehq.apps.reports.filters.fixtures import AsyncLocationFilter
from corehq.apps.reports.graph_models import PieChart
from custom.ewsghana.reports import MultiReport, EWSData
from casexml.apps.stock.models import StockTransaction
from custom.ewsghana.utils import calculate_last_period, get_supply_points
from corehq.apps.reports.filters.dates import DatespanFilter


class AlertsData(EWSData):
    pass


class ReportingRates(EWSData):
    show_table = False
    show_chart = True
    slug = 'reporting_rates'
    title = 'Reporting Rates'

    @property
    def rows(self):
        rows = {}
        if self.config['location_id']:
            supply_points = get_supply_points(self.config['location_id'], self.config['domain'])
            last_period_st, last_period_end = calculate_last_period(self.config['enddate'])
            reports = StockTransaction.objects.filter(case_id__in=supply_points,
                                                      report__date__range=[last_period_st,
                                                                           last_period_end]
                                                      ).distinct('case_id').count()
            rows = dict(
                total=len(supply_points),
                reported=reports,
                non_reported=len(supply_points)-reports
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
                     label='Reported',
                     description="%.2f%% (%d) Reported (last 7 days)" % (reported_percent, data['total'])),
                dict(value=non_reported_percent,
                     label='Non-Reported',
                     description="%.2f%% (%d) Non-Reported (last 7 days)" % (non_reported_percent, data['total'])),
            ]

        return [PieChart('', '', chart_data)]


class ReportingDetails(EWSData):
    show_table = False
    show_chart = True
    slug = 'reporting_details'
    title = 'Reporting Details'

    @property
    def rows(self):
        rows = {}
        if self.config['location_id']:
            last_period_st, last_period_end = calculate_last_period(self.config['enddate'])
            supply_points = get_supply_points(self.config['location_id'], self.config['domain'])
            products_count = SQLProduct.objects.filter(domain=self.config['domain'], is_archived=False).count()
            complete = 0
            incomplete = 0
            for sp in supply_points:
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
                     label='Completed',
                     description="%.2f%% (%d) Complete Reports in last 7 days" % (complete_percent, data['total'])),
                dict(value=incomplete_percent,
                     label='Incompleted',
                     description="%.2f%% (%d) Incomplete Reports in last 7 days" % (incomplete_percent, data['total'])),
            ]

        return [PieChart('', '', chart_data)]

# class SummaryReportingRates(EWSData):
#
#
# class NonReporting(EWSData):
#
#
# class IncompliteReports(EWSData):


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
        )

    @property
    def data_providers(self):
        config = self.report_config
        return [ReportingRates(config=config),
                ReportingDetails(config=config)]