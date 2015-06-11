from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
import pytz
from corehq.apps.es import UserES
from corehq.apps.locations.models import SQLLocation
from corehq.apps.reports.datatables import DataTablesHeader, DataTablesColumn
from corehq.apps.reports.filters.fixtures import AsyncLocationFilter
from corehq.apps.reports.generic import GenericTabularReport
from custom.common import ALL_OPTION
from custom.ewsghana import StockLevelsReport
from custom.ewsghana.filters import ProductByProgramFilter, EWSDateFilter
from custom.ewsghana.reports import MultiReport, ReportingRatesData, ProductSelectionPane, EWSPieChart
from casexml.apps.stock.models import StockTransaction
from custom.ewsghana.reports.stock_levels_report import FacilityReportData, StockLevelsLegend, \
    InventoryManagementData, InputStock, UsersData
from custom.ewsghana.utils import get_country_id, ews_date_format
from custom.ilsgateway.tanzania import make_url
from custom.ilsgateway.tanzania.reports.utils import link_format
from django.utils.translation import ugettext as _
from dimagi.utils.dates import force_to_date
from dimagi.utils.parsing import ISO_DATE_FORMAT
from dimagi.utils.dates import DateSpan
from dimagi.utils.decorators.memoized import memoized
from dimagi.utils.parsing import json_format_date


class ReportingRates(ReportingRatesData):
    show_table = False
    show_chart = True
    slug = 'reporting_rates'
    title = _('Reporting Rates')

    @property
    def rows(self):
        rows = {}
        if self.location_id:
            supply_points = self.location.get_descendants().filter(
                location_type__administrative=False,
                is_archived=False
            )
            reports = self.reporting_supply_points(supply_points.values_list('supply_point_id', flat=True))
            supply_points_count = supply_points.count()
            reports_count = reports.count()
            rows = dict(
                total=supply_points_count,
                reported=reports_count,
                non_reported=supply_points_count - reports_count
            )
        return rows

    @property
    def charts(self):
        data = self.rows
        chart_data = []
        if data:
            reported_percent = float(data['reported']) * 100 / (data['total'] or 1)
            non_reported_percent = float(data['non_reported']) * 100 / (data['total'] or 1)
            reported_formatted = ("%d" if reported_percent.is_integer() else "%.1f") % reported_percent
            non_reported_formatted = ("%d" if non_reported_percent.is_integer() else "%.1f") % non_reported_percent

            chart_data = [
                dict(value=reported_percent,
                     label=_('Reporting'),
                     description=_("%s%% (%d) Reported (%s)" % (reported_formatted, data['reported'],
                                                                self.datetext())),
                     color='green'),
                dict(value=non_reported_percent,
                     label=_('Non-Reporting'),
                     description=_("%s%% (%d) Non-Reported (%s)" %
                                   (non_reported_formatted, data['non_reported'], self.datetext())),
                     color='red'),
            ]
        pie_chart = EWSPieChart('', '', chart_data, ['green', 'red'])
        pie_chart.tooltips = False
        return [pie_chart]


class ReportingDetails(ReportingRatesData):
    show_table = False
    show_chart = True
    slug = 'reporting_details'
    title = _('Reporting Details')

    @property
    def rows(self):
        rows = {}
        if self.location_id:
            supply_points = self.location.get_descendants().filter(
                location_type__administrative=False,
                is_archived=False
            ).values_list('supply_point_id', flat=True)
            complete = 0
            incomplete = 0
            supply_points_ids = self.reporting_supply_points(supply_points)
            transactions = StockTransaction.objects.filter(
                case_id__in=supply_points_ids,
                report__date__range=[self.config['startdate'], self.config['enddate']]
            ).values_list('case_id', 'product_id')
            grouped_by_case = {}
            for (case_id, product_id) in transactions:
                if case_id in grouped_by_case:
                    grouped_by_case[case_id].add(product_id)
                else:
                    grouped_by_case[case_id] = {product_id}

            for case_id, products in grouped_by_case.iteritems():
                location_products = SQLLocation.objects.get(
                    supply_point_id=case_id
                ).products.values_list('product_id', flat=True)
                if not (set(location_products) - products):
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
                     description=_("%.1f%% (%d) Complete Reports in %s" %
                                   (complete_percent, data['complete'], self.datetext())),
                     color='green'),
                dict(value=incomplete_percent,
                     label=_('Incomplete'),
                     description=_("%.1f%% (%d) Incomplete Reports in %s" %
                                   (incomplete_percent, data['incomplete'], self.datetext())),
                     color='purple'),
            ]
        pie_chart = EWSPieChart('', '', chart_data, ['green', 'purple'])
        pie_chart.tooltips = False
        return [pie_chart]


class SummaryReportingRates(ReportingRatesData):

    show_table = True
    show_chart = False
    slug = 'summary_reporting'
    title = _('Summary Reporting Rates')
    use_datatables = True

    @property
    @memoized
    def get_locations(self):
        return SQLLocation.objects.filter(
            domain=self.domain,
            parent__location_id=self.config['location_id'],
            location_type__administrative=True,
            is_archived=False,
        )

    @property
    def headers(self):
        if self.location_id:
            return DataTablesHeader(
                DataTablesColumn(_(self.get_locations[0].location_type.name.title())),
                DataTablesColumn(_('# Sites')),
                DataTablesColumn(_('# Reporting')),
                DataTablesColumn(_('Reporting Rate')),
                DataTablesColumn(_('Completed Report Rates'))
            )
        else:
            return []

    @property
    def rows(self):
        rows = []
        if self.location_id:
            for location in self.get_locations:
                supply_points = self.get_supply_points(location.location_id)
                sites = supply_points.count()
                reported = StockTransaction.objects.filter(
                    case_id__in=supply_points.values_list('supply_point_id', flat=True),
                    report__date__range=[self.config['startdate'], self.config['enddate']]
                ).distinct('case_id').count()
                reporting_rates = '%.2f%%' % (reported * 100 / (float(sites) or 1.0))

                completed = 0
                for supply_point in supply_points:
                    reported_products = StockTransaction.objects.filter(
                        case_id=supply_point.supply_point_id,
                        report__date__range=[self.config['startdate'], self.config['enddate']]
                    ).distinct('product_id').values_list('product_id', flat=True)
                    if not (set(supply_point.products) - set(reported_products)):
                        completed += 1
                completed_rates = '%.2f%%' % (completed * 100 / (float(sites) or 1.0))
                url = make_url(
                    ReportingRatesReport,
                    self.config['domain'],
                    '?location_id=%s&startdate=%s&enddate=%s',
                    (location.location_id, self.config['startdate'], self.config['enddate']))

                rows.append([link_format(location.name, url), sites, reported, reporting_rates, completed_rates])
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
                return _('Non Report RMS and THs')
            else:
                return _('Non Report Facilities')
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

                st = StockTransaction.objects.filter(
                    case_id=location.supply_point_id,
                    report__date__lte=self.config['startdate']
                ).order_by('-report__date')
                if st:
                    date = ews_date_format(st[0].report.date)
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
            supply_points = self.reporting_supply_points()
            for location in SQLLocation.objects.filter(supply_point_id__in=supply_points):
                st = StockTransaction.objects.filter(
                    case_id=location.supply_point_id,
                    report__date__range=[self.config['startdate'], self.config['enddate']]
                ).order_by('-report__date')
                products_per_location = {product.product_id for product in location.products}
                if products_per_location - set(st.values_list('product_id', flat=True)):
                    if st:
                        date = ews_date_format(st[0].report.date)
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
        query = UserES().mobile_users().domain(self.config['domain']).term("location_id",
                                                                           [sp for sp in supply_points])
        with_reporters = set()
        with_in_charge = set()

        for hit in query.run().hits:
            with_reporters.add(hit['location_id'])
            if hit['user_data'].get('role') == 'In Charge':
                with_in_charge.add(hit['location_id'])

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
                    (sp.location_id, json_format_date(self.config['startdate']),
                     json_format_date(self.config['enddate']))
                )
                if sp.supply_point_id not in reported:
                    rows.append(['<div style="background-color: rgba(255, 0, 0, 0.2)">%s has not reported last '
                                 'month. <a href="%s" target="_blank">[details]</a></div>' % (sp.name, url)])
                if sp.location_id not in with_reporters:
                    rows.append(['<div style="background-color: rgba(255, 0, 0, 0.2)">%s has no reporters'
                                 ' registered. <a href="%s" target="_blank">[details]</a></div>' % (sp.name, url)])
                if sp.location_id not in with_in_charge:
                    rows.append(['<div style="background-color: rgba(255, 0, 0, 0.2)">%s has no in-charge '
                                 'registered. <a href="%s" target="_blank">[details]</a></div>' % (sp.name, url)])

        if not rows:
            rows.append(['<div style="background-color: rgba(0, 255, 0, 0.2)">No current alerts</div>'])

        return rows


class EWSDateSpan(DateSpan):

    @classmethod
    def get_date(cls, type=None, month_or_week=None, year=None, format=ISO_DATE_FORMAT,
                 inclusive=True, timezone=pytz.utc):
        if month_or_week is None:
            month_or_week = datetime.datetime.date.today().month
        if year is None:
            year = datetime.datetime.date.today().year
        if type == 2:
            days = month_or_week.split('|')
            start = force_to_date(days[0])
            end = force_to_date(days[1])
        else:
            start = datetime(year, month_or_week, 1)
            end = start + relativedelta(months=1) - relativedelta(days=1)
        return DateSpan(start, end, format, inclusive, timezone)


class MonthWeekMixin(object):
    _datespan = None

    @property
    def datespan(self):
        if self._datespan is None:
            datespan = EWSDateSpan.get_date(self.type, self.first, self.second)
            self.request.datespan = datespan
            self.context.update(dict(datespan=datespan))
            self._datespan = datespan
        return self._datespan

    @property
    def type(self):
        """
            We have a 3 possible type:
            1 - month
            2 - quarter
            3 - year
        """
        if 'datespan_type' in self.request_params:
            return int(self.request_params['datespan_type'])
        else:
            return 1

    @property
    def first(self):
        """
            If we choose type 1 in this we get a month [00-12]
            If we choose type 2 we get quarter [1-4]
            This property is unused when we choose type 3
        """
        if 'datespan_first' in self.request_params:
            try:
                return int(self.request_params['datespan_first'])
            except ValueError:
                return self.request_params['datespan_first']
        else:
            return datetime.utcnow().month

    @property
    def second(self):
        if 'datespan_second' in self.request_params:
            return int(self.request_params['datespan_second'])
        else:
            return datetime.utcnow().year


class ReportingRatesReport(MonthWeekMixin, MultiReport):

    name = 'Reporting'
    title = 'Reporting'
    slug = 'reporting_page'
    fields = [AsyncLocationFilter, ProductByProgramFilter, EWSDateFilter]
    split = False
    is_exportable = True

    def report_filters(self):
        return [f.slug for f in [AsyncLocationFilter, EWSDateFilter]]

    @property
    def report_config(self):
        program = self.request.GET.get('filter_by_program')
        return dict(
            domain=self.domain,
            startdate=self.datespan.startdate,
            enddate=self.datespan.end_of_end_day,
            location_id=self.request.GET.get('location_id') or get_country_id(self.domain),
            products=None,
            program=program if program != ALL_OPTION else None,
            user=self.request.couch_user
        )

    @property
    def data_providers(self):
        config = self.report_config
        if self.is_reporting_type():
            self.split = True
            if self.is_rendered_as_email:
                return [FacilityReportData(config)]
            else:
                return [
                    FacilityReportData(config),
                    StockLevelsLegend(config),
                    InputStock(config),
                    UsersData(config),
                    InventoryManagementData(config),
                    ProductSelectionPane(config, hide_columns=False)
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

        if self.is_rendered_as_email:
            data_providers = [NonReporting(config=config), InCompleteReports(config=config)]
        else:
            data_providers.extend([NonReporting(config=config), InCompleteReports(config=config)])

        return data_providers

    @property
    def export_table(self):
        if self.is_reporting_type():
            return super(ReportingRatesReport, self).export_table

        reports = [self.report_context['reports'][-2]['report_table'],
                   self.report_context['reports'][-1]['report_table']]
        return [self._export(r['title'], r['headers'], r['rows']) for r in reports]

    def _export(self, export_sheet_name, headers, formatted_rows, total_row=None):
        def _unformat_row(row):
            return [col.get("sort_key", col) if isinstance(col, dict) else col for col in row]

        table = headers.as_export_table
        rows = [_unformat_row(row) for row in formatted_rows]
        for row in rows:
            row[0] = GenericTabularReport._strip_tags(row[0])
        replace = ''

        for k, v in enumerate(table[0]):
            if v != ' ':
                replace = v
            else:
                table[0][k] = replace
        table.extend(rows)

        return [export_sheet_name, self._report_info + table]
