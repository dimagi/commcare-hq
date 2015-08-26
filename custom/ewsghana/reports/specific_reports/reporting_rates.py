from django.db.models import Q
from django.http import HttpResponse
from corehq.apps.es import UserES
from corehq.apps.locations.models import SQLLocation, LocationType
from corehq.apps.reports.cache import request_cache
from corehq.apps.reports.datatables import DataTablesHeader, DataTablesColumn
from corehq.apps.reports.generic import GenericTabularReport
from custom.common import ALL_OPTION
from custom.ewsghana import StockLevelsReport
from custom.ewsghana.filters import ProductByProgramFilter, EWSDateFilter, EWSRestrictionLocationFilter
from custom.ewsghana.reports import MultiReport, ReportingRatesData, ProductSelectionPane, EWSPieChart
from casexml.apps.stock.models import StockTransaction
from custom.ewsghana.reports.stock_levels_report import FacilityReportData, StockLevelsLegend, \
    InventoryManagementData, InputStock, UsersData
from custom.ewsghana.utils import get_country_id, ews_date_format
from custom.ilsgateway.tanzania import make_url
from custom.ilsgateway.tanzania.reports.utils import link_format
from django.utils.translation import ugettext as _, ugettext_lazy
from dimagi.utils.decorators.memoized import memoized
from dimagi.utils.parsing import json_format_date


class ReportingRates(ReportingRatesData):
    show_table = False
    show_chart = True
    slug = 'reporting_rates'

    @property
    def title(self):

        if self.config.get('datespan_type') == '1':
            return _('Reporting Rates({}, {})').format(
                self.config['startdate'].strftime('%B'), self.config['startdate'].year
            )
        else:
            return _('Reporting Rates (Weekly Reporting Period)')

    @property
    def rows(self):
        return dict(
            total=self.config['all'],
            reported=self.config['complete'] + self.config['incomplete'],
            non_reported=self.config['non_reporting']
        )

    @property
    def charts(self):
        data = self.rows
        chart_data = []
        if data:
            reported_percent = round((data['reported']) * 100 / (data['total'] or 1))
            non_reported_percent = round((data['non_reported']) * 100 / (data['total'] or 1))
            reported_formatted = ("%d" if reported_percent.is_integer() else "%.1f") % reported_percent
            non_reported_formatted = ("%d" if non_reported_percent.is_integer() else "%.1f") % non_reported_percent

            chart_data = sorted([
                dict(value=non_reported_percent,
                     label=_('Non-Reporting %s%%' % non_reported_formatted),
                     description=_("%s%% (%d) Non-Reported (%s)" %
                                   (non_reported_formatted, data['non_reported'], self.datetext())),
                     color='red'),
                dict(value=reported_percent,
                     label=_('Reporting %s%%' % reported_formatted),
                     description=_("%s%% (%d) Reported (%s)" % (reported_formatted, data['reported'],
                                                                self.datetext())),
                     color='green'),
            ], key=lambda x: x['value'], reverse=True)
        pie_chart = EWSPieChart('', '', chart_data, [chart_data[0]['color'], chart_data[1]['color']])
        pie_chart.tooltips = False
        return [pie_chart]


class ReportingDetails(ReportingRatesData):
    show_table = False
    show_chart = True
    slug = 'reporting_details'

    @property
    def title(self):
        if self.config.get('datespan_type') == '1':
            return _('Reporting Details({}, {})').format(
                self.config['startdate'].strftime('%B'), self.config['startdate'].year
            )
        else:
            return _('Reporting Details (Weekly Reporting Period)')

    @property
    def rows(self):
        if self.location_id:
            return dict(
                total=self.config['complete'] + self.config['incomplete'],
                complete=self.config['complete'],
                incomplete=self.config['incomplete']
            )
        return {}

    @property
    def charts(self):
        data = self.rows
        chart_data = []
        if data:
            complete_percent = round((data['complete']) * 100 / (data['total'] or 1))
            incomplete_percent = round((data['incomplete']) * 100 / (data['total'] or 1))
            complete_formatted = ("%d" if complete_percent.is_integer() else "%.1f") % complete_percent
            incomplete_formatted = ("%d" if incomplete_percent.is_integer() else "%.1f") % incomplete_percent
            chart_data = [
                dict(value=complete_formatted,
                    label=_('Complete %s%%') % complete_formatted,
                    description=_("%s%% (%d) Complete Reports in %s") %
                        (complete_formatted, data['complete'], self.datetext()),
                    color='green'),
                dict(value=incomplete_formatted,
                    label=_('Incomplete %s%%') % incomplete_formatted,
                    description=_("%s%% (%d) Incomplete Reports in %s") %
                        (incomplete_formatted, data['incomplete'], self.datetext()),
                    color='purple'),
            ]
        pie_chart = EWSPieChart('', '', chart_data, ['green', 'purple'])
        pie_chart.tooltips = False
        return [pie_chart]


class SummaryReportingRates(ReportingRatesData):

    show_table = True
    show_chart = False
    slug = 'summary_reporting'
    title = ugettext_lazy('Summary Reporting Rates')
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
            for location_name, values in self.config['summary_reporting_rates'].iteritems():
                url = make_url(
                    ReportingRatesReport,
                    self.config['domain'],
                    '?location_id=%s&startdate=%s&enddate=%s',
                    (values['location_id'], self.config['startdate'], self.config['enddate'])
                )
                is_rendered_as_email = self.config['is_rendered_as_email']
                rows.append(
                    [
                        link_format(location_name, url) if not is_rendered_as_email else location_name,
                        values['all'],
                        values['complete'] + values['incomplete'],
                        '%d%%' % (100 * (values['complete'] + values['incomplete']) / (values['all'] or 1)),
                        '%d%%' % (100 * values['complete'] / (values['all'] or 1))
                    ]
                )
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
                return _('Non-Reporting Medical Stores and Teaching Hospitals')
            else:
                return _('Non-Reporting Facilities')
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
            for name, location_id, date, supply_point_id in self.config['non_reporting_table']:
                url = make_url(
                    StockLevelsReport,
                    self.config['domain'],
                    '?location_id=%s&startdate=%s&enddate=%s',
                    (location_id, self.config['startdate'], self.config['enddate'])
                )

                st = StockTransaction.objects.filter(
                    case_id=supply_point_id,
                    report__date__lte=self.config['startdate']
                ).select_related('report__date').order_by('-report__date')
                if st:
                    date = ews_date_format(st[0].report.date)
                else:
                    date = '---'
                rows.append([link_format(name, url) if not self.config['is_rendered_as_email'] else name, date])
        return rows


class InCompleteReports(ReportingRatesData):

    show_table = True
    show_chart = False
    slug = 'incomplete_reporting'
    title = ugettext_lazy('Incomplete Reports')
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
            for name, location_id, date in self.config['incomplete_table']:
                url = make_url(
                    StockLevelsReport,
                    self.config['domain'],
                    '?location_id=%s&startdate=%s&enddate=%s',
                    (location_id, self.config['startdate'], self.config['enddate'])
                )
                rows.append(
                    [
                        link_format(name, url) if not self.config['is_rendered_as_email'] else name,
                        ews_date_format(date)
                    ]
                )
        return rows


class AlertsData(ReportingRatesData):
    show_table = True
    show_chart = False
    slug = 'alerts'
    title = ugettext_lazy('Alerts')

    @property
    def headers(self):
        return []

    def supply_points_users(self):
        query = UserES().mobile_users().domain(self.config['domain']).term(
            "location_id", list(self.config['reporting_supply_points'])
        )
        with_reporters = set()
        with_in_charge = set()

        for hit in query.run().hits:
            with_reporters.add(hit['location_id'])
            if 'In Charge' in hit['user_data'].get('role', []):
                with_in_charge.add(hit['location_id'])

        return with_reporters, with_in_charge

    @property
    def rows(self):
        rows = []
        if self.location_id:
            supply_points = self.get_supply_points()
            with_reporters, with_in_charge = self.supply_points_users()
            for sp in supply_points:
                url = make_url(
                    StockLevelsReport, self.config['domain'], '?location_id=%s&startdate=%s&enddate=%s',
                    (sp.location_id, json_format_date(self.config['startdate']),
                     json_format_date(self.config['enddate']))
                )
                if sp.supply_point_id not in self.config['reporting_supply_points']:
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


class ReportingRatesReport(MultiReport):

    name = 'Reporting'
    title = 'Reporting'
    slug = 'reporting_page'
    split = False
    is_exportable = True

    @property
    def fields(self):
        if self.is_reporting_type():
            return [EWSRestrictionLocationFilter, ProductByProgramFilter]
        return [EWSRestrictionLocationFilter, ProductByProgramFilter, EWSDateFilter]

    def get_supply_points(self, location_id):
        sql_location = SQLLocation.objects.get(location_id=location_id)
        if sql_location.location_type.name == 'district':
            locations = SQLLocation.objects.filter(parent=sql_location)
        elif sql_location.location_type.name == 'region':
            loc_types = LocationType.objects.filter(
                administrative=False,
                domain=self.domain
            ).exclude(name='Central Medical Store')
            locations = SQLLocation.objects.filter(
                Q(parent__parent=sql_location, location_type__in=loc_types) |
                Q(parent=sql_location, location_type__in=loc_types)
            )
        elif not sql_location.location_type.administrative:
            locations = SQLLocation.objects.filter(id=sql_location.id)
        else:
            types = ['Central Medical Store', 'Regional Medical Store', 'Teaching Hospital']
            locations = SQLLocation.objects.filter(
                domain=self.domain,
                location_type__name__in=types
            )
        return locations.exclude(supply_point_id__isnull=True).exclude(is_archived=True)

    def reporting_rates(self):
        complete = 0
        incomplete = 0
        all_locations_count = self.report_location.get_descendants().count()
        transactions = self.get_stock_transactions().values_list('case_id', 'product_id', 'report__date')
        grouped_by_case = {}
        parent_sum_rates = {}
        locations_ids = set()
        supply_points = list(self.get_supply_points(
            self.report_config['location_id']
        ))
        report_status = {
            supply_point.supply_point_id: {
                'status': 'non_reporting',
                'name': supply_point.name,
                'location_id': supply_point.location_id,
                'date': None
            }
            for supply_point in supply_points
        }
        aggregate_type = None
        if self.report_location.location_type.name == 'country':
            aggregate_type = 'region'
        elif self.report_location.location_type.name == 'region':
            aggregate_type = 'district'
        if aggregate_type:
            for location in self.report_location.get_children().filter(location_type__administrative=True):
                parent_sum_rates[location.name] = {
                    'complete': 0,
                    'incomplete': 0,
                    'location_id': location.location_id,
                    'all': location.get_descendants().filter(location_type__administrative=False).count()
                }

        for (case_id, product_id, date) in transactions:
            if case_id in report_status:
                report_status[case_id]['date'] = date

            if case_id in grouped_by_case:
                grouped_by_case[case_id].add(product_id)
            else:
                grouped_by_case[case_id] = {product_id}

        for case_id, products in grouped_by_case.iteritems():
            location = SQLLocation.objects.get(
                supply_point_id=case_id
            )
            locations_ids.add(location.location_id)

            aggregate_location = None

            if aggregate_type:
                aggregate_location = location.get_ancestors(ascending=True).filter(
                    location_type__name=aggregate_type
                )

            if aggregate_location:
                aggregate_location = aggregate_location[0]

            if not (set(location.products.values_list('product_id', flat=True)) - products):
                complete += 1
                if case_id in report_status:
                    report_status[case_id]['status'] = 'complete'
                if aggregate_type and aggregate_location:
                    parent_sum_rates[aggregate_location.name]['complete'] += 1
            else:
                incomplete += 1
                if case_id in report_status:
                    report_status[case_id]['status'] = 'incomplete'
                if aggregate_location:
                    parent_sum_rates[aggregate_location.name]['incomplete'] += 1

        return {
            'all': all_locations_count,
            'complete': complete,
            'incomplete': incomplete,
            'reporting_supply_points': locations_ids,
            'summary_reporting_rates': parent_sum_rates,
            'non_reporting': all_locations_count - (complete + incomplete),
            'non_reporting_table': [
                [status['name'], status['location_id'], status['date'], key]
                for key, status in report_status.iteritems()
                if not status['date']
            ],
            'incomplete_table': [
                [status['name'], status['location_id'], status['date']]
                for key, status in report_status.iteritems()
                if status['status'] == 'incomplete'
            ]
        }

    def report_filters(self):
        return [f.slug for f in [EWSRestrictionLocationFilter, EWSDateFilter]]

    @property
    def report_config(self):
        program = self.request.GET.get('filter_by_program')
        return dict(
            domain=self.domain,
            startdate=self.datespan.startdate,
            enddate=self.datespan.enddate,
            location_id=self.request.GET.get('location_id') or get_country_id(self.domain),
            products=None,
            program=program if program != ALL_OPTION else None,
            user=self.request.couch_user,
            datespan_type=self.request.GET.get('datespan_type'),
            is_rendered_as_email=self.is_rendered_as_email
        )

    @property
    def print_providers(self):
        config = self.report_config
        config.update(self.reporting_rates())
        config.update({'is_rendered_as_print': self.is_rendered_as_print})
        providers = [
            ReportingRates(config=config),
            ReportingDetails(config=config),
            NonReporting(config=config),
            InCompleteReports(config=config)
        ]
        location = self.active_location
        if location.location_type.name.lower() in ['country', 'region']:
            providers.insert(2, SummaryReportingRates(config=config))

        return providers

    @property
    def email_providers(self):
        config = self.report_config
        config.update(self.reporting_rates())
        config.update({'is_rendered_as_email': self.is_rendered_as_email})
        providers = [
            NonReporting(config=config),
            InCompleteReports(config=config)
        ]
        if self.active_location.location_type.name.lower() in ['country', 'region']:
            providers = [SummaryReportingRates(config=config)] + providers

        return providers

    @property
    def data_providers(self):
        config = self.report_config
        if self.is_reporting_type():
            self.split = True
            if self.is_rendered_as_email and self.is_rendered_as_print:
                return [FacilityReportData(config), InventoryManagementData(config)]
            elif self.is_rendered_as_email:
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
        config.update(self.reporting_rates())
        if self.is_rendered_as_print:
            return self.print_providers
        elif self.is_rendered_as_email:
            return self.email_providers

        data_providers = [
            AlertsData(config=config),
            ReportingRates(config=config),
            ReportingDetails(config=config)
        ]
        location = SQLLocation.objects.get(location_id=config['location_id'])
        if config['location_id'] and location.location_type.name.lower() in ['country', 'region']:
            data_providers.append(SummaryReportingRates(config=config))

        data_providers.extend([
            NonReporting(config=config),
            InCompleteReports(config=config)
        ])
        return data_providers

    @property
    def export_table(self):
        if self.is_reporting_type():
            return super(ReportingRatesReport, self).export_table
        non_reporting = self.report_context['reports'][-2]['report_table']
        non_reporting['title'] = 'Non reporting'
        reports = [non_reporting,
                   self.report_context['reports'][-1]['report_table']]
        if self.report_location.location_type.name.lower() in ['country', 'region']:
            reports = [self.report_context['reports'][-3]['report_table']] + reports
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

    @property
    @request_cache()
    def print_response(self):
        """
        Returns the report for printing.
        """
        self.is_rendered_as_print = True
        self.is_rendered_as_email = True
        self.use_datatables = False
        if self.is_reporting_type():
            self.override_template = 'ewsghana/facility_page_print_report.html'
        else:
            self.override_template = 'ewsghana/reporting_rates_print_report.html'
        return HttpResponse(self._async_context()['report'])
