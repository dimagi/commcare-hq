import calendar
import datetime
from corehq.apps.reports.graph_models import MultiBarChart, Axis, PieChart, LineChart
from corehq.apps.reports.sqlreport import calculate_total_row
from corehq.apps.reports.standard import ProjectReportParametersMixin, DatespanMixin, CustomProjectReport
from custom.world_vision.sqldata import LOCATION_HIERARCHY
from custom.world_vision.sqldata.child_sqldata import NutritionBirthWeightDetails, ClosedChildCasesBreakdown, \
    ChildrenDeathsByMonth
from custom.world_vision.sqldata.main_sqldata import ImmunizationOverview
from custom.world_vision.sqldata.mother_sqldata import ClosedMotherCasesBreakdown, DeliveryLiveBirthDetails, \
    PostnatalCareOverview, AnteNatalCareServiceOverviewExtended, DeliveryPlaceDetailsExtended
from dimagi.utils.decorators.memoized import memoized


class TTCReport(ProjectReportParametersMixin, CustomProjectReport):
    report_template_path = "world_vision/multi_report.html"

    title = ''
    flush_layout = True
    export_format_override = 'csv'

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
        context = {
            'reports': [self.get_report_context(dp) for dp in self.data_providers],
            'title': self.title
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
            health_center_worker = 'health_center_worker',
            trained_traditional_birth_attendant = 'trained_traditional_birth_attendant',
            normal_delivery = 'normal',
            cesarean_delivery = 'cesarean',
            unknown_delivery = 'unknown',
            abortion = 'abortion',
            weight_birth_25 = '2.5'
        )

        if 'startdate' in self.request.GET and self.request.GET['startdate']:
            config['startdate'] = self.request.GET['startdate']
            config['strsd'] = self.request.GET['startdate']
        if 'enddate' in self.request.GET and self.request.GET['enddate']:
            config['enddate'] = self.request.GET['enddate']
            config['stred'] = self.request.GET['enddate']

        today = datetime.date.today()
        config['today'] = today.strftime("%Y-%m-%d")

        for d in [2, 5, 21, 40, 75, 84, 106, 168, 182, 183, 195, 224, 245, 273, 365, 547, 548, 700, 730]:
            config['days_%d' % d] = (today - datetime.timedelta(days=d)).strftime("%Y-%m-%d")

        for d in [1, 3, 5, 6]:
            config['%d' % d] = '%d' % d

        config['last_month'] = (today - datetime.timedelta(days=30)).strftime("%Y-%m-%d")
        config['first_trimester_start_date'] = (today - datetime.timedelta(days=84)).strftime("%Y-%m-%d")
        config['second_trimester_start_date'] = (today - datetime.timedelta(days=84)).strftime("%Y-%m-%d")
        config['second_trimester_end_date'] = (today - datetime.timedelta(days=196)).strftime("%Y-%m-%d")
        config['third_trimester_start_date'] =  (today - datetime.timedelta(days=196)).strftime("%Y-%m-%d")

        for k, v in sorted(LOCATION_HIERARCHY.iteritems(), reverse=True):
            req_prop = 'location_%s' % v['prop']
            if self.request.GET.getlist(req_prop, []):
                location_list = self.request.GET.getlist(req_prop, [])
                if location_list and location_list[0] != '0':
                    config.update({k: tuple(location_list)})
                    break
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
                fix_column=data_provider.fix_left_col
            ),
            charts=charts,
            chart_span=12
        )

        return context

    def get_chart(self, rows, x_label, y_label, data_provider):
        if isinstance(data_provider, (ClosedMotherCasesBreakdown, ClosedChildCasesBreakdown)):
            chart = PieChart('', '', [{'label': row[0], 'value':float(row[-1]['html'][:-1])} for row in rows])
        elif isinstance(data_provider, NutritionBirthWeightDetails):
            chart = PieChart('BirthWeight', '', [{'label': row[0]['html'], 'value':float(row[-1]['html'][:-1])} for row in rows[1:]])
        elif isinstance(data_provider, DeliveryPlaceDetailsExtended):
            chart = PieChart('', '', [{'label': row[0]['html'], 'value':float(row[-1]['html'][:-1])} for row in rows[1:]])
        elif isinstance(data_provider, (PostnatalCareOverview, ImmunizationOverview)):
            chart = MultiBarChart('', x_axis=Axis(x_label), y_axis=Axis(y_label, '.2%'))
            chart.rotateLabels = -45
            chart.marginBottom = 120
            if isinstance(data_provider, ImmunizationOverview):
                chart.stacked = True
                chart.add_dataset('Percentage', [{'x': row[0]['html'], 'y':float(row[3]['html'][:-1])/100} for row in rows])
                chart.add_dataset('Dropout Percentage', [{'x': row[0]['html'], 'y':float(row[-1]['html'][:-1])/100} for row in rows])
            else:
                chart.add_dataset('Percentage', [{'x': row[0]['html'], 'y':float(row[-1]['html'][:-1])/100} for row in rows])
        elif isinstance(data_provider, AnteNatalCareServiceOverviewExtended):
            chart1 = MultiBarChart('', x_axis=Axis(x_label), y_axis=Axis(y_label, '.2%'))
            chart2 = MultiBarChart('', x_axis=Axis(x_label), y_axis=Axis(y_label, '.2%'))
            chart1.rotateLabels = -45
            chart2.rotateLabels = -45
            chart1.marginBottom = 120
            chart2.marginBottom = 120
            chart1.add_dataset('Percentage', [{'x': row[0]['html'], 'y':float(row[-1]['html'][:-1])/100} for row in rows[1:6]])
            chart2.add_dataset('Percentage', [{'x': row[0]['html'], 'y':float(row[-1]['html'][:-1])/100} for row in rows[6:12]])
            return [chart1, chart2]
        elif isinstance(data_provider, ChildrenDeathsByMonth):
            chart = LineChart('Seasonal Variation of Child Deaths', x_axis=Axis(x_label, dateFormat="%B"), y_axis=Axis(y_label, '.2%'))
            chart.rotateLabels = -45
            chart.marginBottom = 120
            months_mapping = dict((v,k) for k,v in enumerate(calendar.month_abbr))
            chart.add_dataset('Percentage', [{'x': datetime.date(1, months_mapping[row[0][:3]], 1),
                                              'y':float(row[-1]['html'][:-1])/100} for row in rows])
        else:
            chart = PieChart('', '', [{'label': row[0]['html'], 'value':float(row[-1]['html'][:-1])} for row in rows])
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

