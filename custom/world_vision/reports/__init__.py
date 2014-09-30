import datetime
from corehq.apps.reports.graph_models import MultiBarChart, Axis, PieChart
from corehq.apps.reports.sqlreport import calculate_total_row
from corehq.apps.reports.standard import ProjectReportParametersMixin, DatespanMixin, CustomProjectReport
from dimagi.utils.decorators.memoized import memoized
from custom.world_vision.sqldata import MotherRegistrationOverview, ClosedMotherCasesBreakdown, PregnantMotherBreakdownByTrimester, DeliveryLiveBirthDetails, NutritionBirthWeightDetails, PostnatalCareOverview, ImmunizationOverview, ClosedChildCasesBreakdown, \
    LOCATION_HIERARCHY


class TTCReport(ProjectReportParametersMixin, DatespanMixin, CustomProjectReport):
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
            startdate=self.datespan.startdate,
            enddate=self.datespan.enddate,
            empty='',
            yes='yes',
            death='death',
            strsd=self.datespan.startdate.strftime("%Y-%m-%d"),
            stred=self.datespan.enddate.strftime("%Y-%m-%d"),
            pregnant_mother_type = 'pregnant',
            health_center = 'health center',
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

        today = datetime.date.today()
        config['today'] = today.strftime("%Y-%m-%d")
        config['last_month'] = (today - datetime.timedelta(days=30)).strftime("%Y-%m-%d"),
        config['days_2'] = (today - datetime.timedelta(days=2)).strftime("%Y-%m-%d"),
        config['days_5'] = (today - datetime.timedelta(days=5)).strftime("%Y-%m-%d"),
        config['days_21'] = (today - datetime.timedelta(days=21)).strftime("%Y-%m-%d"),
        config['days_106'] = (today - datetime.timedelta(days=106)).strftime("%Y-%m-%d"),
        config['days_182'] = (today - datetime.timedelta(days=182)).strftime("%Y-%m-%d"),
        config['days_183'] = (today - datetime.timedelta(days=183)).strftime("%Y-%m-%d"),
        config['days_195'] = (today - datetime.timedelta(days=195)).strftime("%Y-%m-%d"),
        config['days_224'] = (today - datetime.timedelta(days=224)).strftime("%Y-%m-%d"),
        config['days_273'] = (today - datetime.timedelta(days=273)).strftime("%Y-%m-%d"),
        config['days_548'] = (today - datetime.timedelta(days=548)).strftime("%Y-%m-%d"),
        config['days_700'] = (today - datetime.timedelta(days=700)).strftime("%Y-%m-%d"),
        config['days_730'] = (today - datetime.timedelta(days=730)).strftime("%Y-%m-%d"),
        config['first_trimester_start_date'] = (today - datetime.timedelta(days=84)).strftime("%Y-%m-%d")
        config['second_trimester_start_date'] = (today - datetime.timedelta(days=84)).strftime("%Y-%m-%d")
        config['second_trimester_end_date'] = (today - datetime.timedelta(days=196)).strftime("%Y-%m-%d")
        config['third_trimester_start_date'] =  (today - datetime.timedelta(days=196)).strftime("%Y-%m-%d")

        for k, v in sorted(LOCATION_HIERARCHY.iteritems(), reverse=True):
            req_prop = 'location_%s' % v['prop']
            if self.request.GET.getlist(req_prop, []):
                config.update({k: tuple(self.request.GET.getlist(req_prop, []))})
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
        if isinstance(data_provider, ClosedMotherCasesBreakdown) or isinstance(data_provider, ClosedChildCasesBreakdown):
            chart = PieChart('', '', [{'label': row[0], 'value':float(row[-1]['html'][:-1])} for row in rows])
        elif isinstance(data_provider, DeliveryLiveBirthDetails):
            chart = PieChart('Live Births by Gender', '', [{'label': row[0]['html'], 'value':float(row[-1]['html'][:-1])} for row in rows[1:]])
        elif isinstance(data_provider, NutritionBirthWeightDetails):
            chart = PieChart('BirthWeight', '', [{'label': row[0]['html'], 'value':float(row[-1]['html'][:-1])} for row in rows[1:]])
        elif isinstance(data_provider, PostnatalCareOverview) or isinstance(data_provider, ImmunizationOverview):
            chart = MultiBarChart('', x_axis=Axis(x_label), y_axis=Axis(y_label, '.2%'))
            chart.rotateLabels = -45
            chart.marginBottom = 120
            if isinstance(data_provider, ImmunizationOverview):
                chart.stacked = True
                chart.add_dataset('Percentage', [{'x': row[0]['html'], 'y':float(row[3]['html'][:-1])/100} for row in rows])
                chart.add_dataset('Dropout Percentage', [{'x': row[0]['html'], 'y':float(row[-1]['html'][:-1])/100} for row in rows])
            else:
                chart.add_dataset('Percentage', [{'x': row[0]['html'], 'y':float(row[-1]['html'][:-1])/100} for row in rows])
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

