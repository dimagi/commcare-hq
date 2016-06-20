import datetime
from collections import OrderedDict

from django.http import HttpResponse

from corehq.apps.reports.cache import request_cache
from corehq.apps.reports.graph_models import MultiBarChart, Axis
from corehq.apps.style.decorators import use_nvd3
from custom.world_vision.charts import WVPieChart as PieChart
from corehq.apps.reports.sqlreport import calculate_total_row
from corehq.apps.reports.standard import ProjectReportParametersMixin, CustomProjectReport
from custom.world_vision.sqldata import LOCATION_HIERARCHY
from custom.world_vision.sqldata.child_sqldata import NutritionBirthWeightDetails,  ChildrenDeathsByMonth
from custom.world_vision.sqldata.main_sqldata import ImmunizationOverview
from custom.world_vision.sqldata.mother_sqldata import PostnatalCareOverview, AnteNatalCareServiceOverviewExtended, \
    DeliveryPlaceDetailsExtended
from dimagi.utils.decorators.memoized import memoized
from dimagi.utils.parsing import json_format_date


class TTCReport(ProjectReportParametersMixin, CustomProjectReport):
    report_template_path = "world_vision/multi_report.html"
    is_mixed_report = False
    title = ''
    flush_layout = True
    export_format_override = 'csv'
    printable = True

    @use_nvd3
    def decorator_dispatcher(self, request, *args, **kwargs):
        super(TTCReport, self).decorator_dispatcher(request, *args, **kwargs)

    @property
    @memoized
    def rendered_report_title(self):
        return self.title

    @property
    @memoized
    def data_providers(self):
        return []

    @property
    def report_context(self):
        reports = OrderedDict()
        for dp in self.data_providers:
            reports[dp.slug] = self.get_report_context(dp)
        context = {
            'reports': reports,
            'title': "%s (%s-%s)" % (self.title, self.report_config.get('strsd', '-'),
                                     self.report_config.get('stred', '-'))
        }

        return context

    @property
    def report_config(self):
        config = dict(
            domain=self.domain,
            empty='',
            yes='yes',
            no='no',
            death='death',
            pregnant_mother_type = 'pregnant',
            health_center = 'health_center',
            hospital = 'hospital',
            home = 'home',
            on_route = 'on_route',
            other = 'other',
            male  = 'male',
            female = 'female',
            health_center_worker = 'health_center_worker',
            trained_traditional_birth_attendant = 'trained_traditional_birth_attendant',
            normal_delivery = 'normal',
            cesarean_delivery = 'cesarean',
            unknown_delivery = 'unknown',
            abortion = 'abortion',
            weight_birth_25='2.5',
            newborn_death='newborn_death',
            infant_death='infant_death',
            child_death='child_death',
            date_of_death='date_of_death'
        )

        if 'startdate' in self.request.GET and self.request.GET['startdate']:
            config['startdate'] = self.request.GET['startdate']
            config['strsd'] = self.request.GET['startdate']
        if 'enddate' in self.request.GET and self.request.GET['enddate']:
            config['enddate'] = self.request.GET['enddate']
            config['stred'] = self.request.GET['enddate']

        today = datetime.date.today()
        config['today'] = json_format_date(today)

        for d in [35, 56, 84, 85, 112, 196]:
            config['today_plus_%d' % d] = json_format_date(today + datetime.timedelta(days=d))

        for d in [2, 4, 21, 25, 40, 42, 75, 106, 182, 183, 273, 365, 547, 548, 700, 730]:
            config['today_minus_%d' % d] = json_format_date(today - datetime.timedelta(days=d))

        for d in [1, 3, 5, 6]:
            config['%d' % d] = '%d' % d

        config['last_month'] = json_format_date(today - datetime.timedelta(days=30))

        for k, v in sorted(LOCATION_HIERARCHY.iteritems(), reverse=True):
            req_prop = 'location_%s' % v['prop']
            if self.request.GET.getlist(req_prop, []):
                location_list = self.request.GET.getlist(req_prop, [])
                if location_list and location_list[0] != '0':
                    config.update({k: tuple(location_list)})
        return config

    def get_report_context(self, data_provider):
        total_row = []
        charts = []
        self.data_source = data_provider
        if self.needs_filters:
            headers = []
            rows = []
        else:
            headers = data_provider.headers
            rows = data_provider.rows

            if data_provider.show_total:
                if data_provider.custom_total_calculate:
                    total_row = data_provider.calculate_total_row(rows)
                else:
                    total_row = list(calculate_total_row(rows))
                if total_row:
                    total_row[0] = data_provider.total_row_name

            if data_provider.show_charts:
                charts = list(self.get_chart(
                    rows,
                    x_label=data_provider.chart_x_label,
                    y_label=data_provider.chart_y_label,
                    data_provider=data_provider
                ))

        context = dict(
            report_table=dict(
                title=data_provider.title,
                slug=data_provider.slug,
                headers=headers,
                rows=rows,
                total_row=total_row,
                datatables=data_provider.datatables,
                start_at_row=0,
                fix_column=data_provider.fix_left_col,
                accordion_start=data_provider.accordion_start,
                accordion_end=data_provider.accordion_end,
                chart_only=data_provider.chart_only and self.is_mixed_report,
                table_only=data_provider.table_only and self.is_mixed_report,
                is_mixed_report=self.is_mixed_report
            ),
            charts=charts,
            chart_span=12
        )
        return context

    def get_chart(self, rows, x_label, y_label, data_provider):
        def _get_label_with_percentage(row):
            return "%s [%d: %s%%]" % (row[0]['html'], int(row[-2]['html']), str(int(row[-1]['html'][:-1])))

        if isinstance(data_provider, NutritionBirthWeightDetails):
            chart = PieChart(data_provider.chart_title, '',
                             [{'label': _get_label_with_percentage(row),
                               'value': int(row[-1]['html'][:-1])} for row in rows[2:]], ['red', 'green'])
            chart.showLabels = False
            chart.marginLeft = 20
            chart.marginRight = 0
            chart.marginBottom = 20
        elif isinstance(data_provider, DeliveryPlaceDetailsExtended):
            chart = PieChart(data_provider.chart_title, '',
                             [{'label': _get_label_with_percentage(row),
                               'value': int(row[-1]['html'][:-1])} for row in rows[1:]])
            chart.showLabels = False
        elif isinstance(data_provider, (PostnatalCareOverview, ImmunizationOverview)):
            chart = MultiBarChart(data_provider.chart_title, x_axis=Axis(x_label), y_axis=Axis(y_label, '.2%'))
            chart.rotateLabels = -45
            chart.marginBottom = 150
            chart.marginLeft = 45
            chart.marginRight = 0

            if isinstance(data_provider, ImmunizationOverview):
                chart.stacked = True
                chart.add_dataset('Percentage',
                                  [{'x': row[0]['html'],
                                    'y': int(row[3]['html'][:-1]) / 100.0} for row in rows],
                                  color='green')
                chart.add_dataset('Dropout Percentage',
                                  [{'x': row[0]['html'],
                                    'y': int(row[-1]['html'][:-1]) / 100.0} for row in rows],
                                  color='red')
            else:
                chart.add_dataset('Percentage',
                                  [{'x': row[0]['html'], 'y':int(row[-1]['html'][:-1]) / 100.0} for row in rows])
        elif isinstance(data_provider, AnteNatalCareServiceOverviewExtended):
            chart1 = MultiBarChart('ANC Visits', x_axis=Axis(x_label), y_axis=Axis(y_label, '.2%'))
            chart2 = MultiBarChart('Maternal TT & IFA', x_axis=Axis(x_label), y_axis=Axis(y_label, '.2%'))
            chart1.rotateLabels = -45
            chart2.rotateLabels = -45
            chart1.marginBottom = 150
            chart2.marginBottom = 150
            chart1.marginLeft = 20
            chart2.marginLeft = 45
            chart1.marginRight = 0
            chart2.marginRight = 0

            chart1.add_dataset('Percentage', [{'x': row[0]['html'],
                                               'y': int(row[-1]['html'][:-1]) / 100.0} for row in rows[1:6]])
            chart2.add_dataset('Percentage', [{'x': row[0]['html'],
                                               'y': int(row[-1]['html'][:-1]) / 100.0} for row in rows[6:12]])
            return [chart1, chart2]
        elif isinstance(data_provider, ChildrenDeathsByMonth):
            chart = MultiBarChart(data_provider.chart_title, x_axis=Axis(x_label, dateFormat="%B"),
                                  y_axis=Axis(y_label, '.2%'))
            chart.rotateLabels = -45
            chart.marginBottom = 50
            chart.marginLeft = 20
            chart.add_dataset('Percentage', [{'x': row[0],
                                              'y': int(row[-1]['html'][:-1]) / 100.0} for row in rows])
        else:
            chart = PieChart(data_provider.chart_title, '', [{'label': _get_label_with_percentage(row),
                                                              'value': int(row[-1]['html'][:-1])} for row in rows])
            chart.showLabels = False
            chart.marginLeft = 20
            chart.marginRight = 0
            chart.marginBottom = 0
        return [chart]

    @property
    def export_table(self):
        reports = [r['report_table'] for r in self.report_context['reports']]
        return [self._export_table(r['title'], r['headers'], r['rows'], total_row=r['total_row']) for r in reports]

    def _export_table(self, export_sheet_name, headers, formatted_rows, total_row=None):
        def _unformat_row(row):
            return [col.get("sort_key", col) if isinstance(col, dict) else col for col in row]

        table = headers.as_export_table
        rows = [_unformat_row(row) for row in formatted_rows]
        replace = ''

        #make headers and subheaders consistent
        for k, v in enumerate(table[0]):
            if v != ' ':
                replace = v
            else:
                table[0][k] = replace
        table.extend(rows)
        if total_row:
            table.append(_unformat_row(total_row))

        return [export_sheet_name, table]

    @property
    def email_response(self):
        return super(TTCReport, self).email_response

    @property
    @request_cache()
    def print_response(self):
        """
        Returns the report for printing.
        """
        self.is_rendered_as_email = True
        self.use_datatables = False
        self.override_template = "world_vision/print_report.html"
        return HttpResponse(self._async_context()['report'])


class AccordionTTCReport(TTCReport):
    report_template_path = 'world_vision/accordion_report.html'

    @property
    def report_context(self):
        reports = []
        for dp_list in self.data_providers:
            helper_list = []
            for dp in dp_list:
                helper_list.append(self.get_report_context(dp))
            reports.append(helper_list)
        return {
            'reports': reports,
            'title': "%s (%s-%s)" % (self.title, self.report_config.get('strsd', '-'),
                                     self.report_config.get('stred', '-'))
        }
