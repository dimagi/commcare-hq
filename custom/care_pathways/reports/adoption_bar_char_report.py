from corehq.apps.reports.graph_models import MultiBarChart, Axis
from corehq.apps.reports.datatables import DataTablesHeader
from corehq.apps.reports.sqlreport import DataFormatter, TableDataFormat
from custom.care_pathways.filters import GeographyFilter, GenderFilter, GroupLeadershipFilter, CBTNameFilter,  GroupByFilter, PPTYearFilter, TypeFilter, ScheduleFilter, \
    RealOrTestFilter, MalawiPPTYearFilter
from custom.care_pathways.reports import CareBaseReport
from custom.care_pathways.sqldata import AdoptionBarChartReportSqlData
import re

class AdoptionBarChartReport(CareBaseReport):
    name = 'Adoption Bar Chart'
    slug = 'adoption_bar_chart'
    report_title = 'Adoption Bar Chart'
    report_template_path = 'care_pathways/adoption_bar_chart_report.html'

    @property
    def fields(self):
        filters = [GeographyFilter]
        if self.domain == 'care-macf-malawi':
            filters.append(MalawiPPTYearFilter)
        else:
            filters.append(PPTYearFilter)
        filters.extend([
            GenderFilter,
            GroupLeadershipFilter,
            CBTNameFilter
        ])
        if self.domain == 'care-macf-malawi':
            filters.append(RealOrTestFilter)
        if self.domain == 'pathways-india-mis':
            filters.append(ScheduleFilter)
        filters.append(TypeFilter)
        filters.append(GroupByFilter)
        print self.report_template_path

        return filters

    @property
    def report_config(self):
        config = super(AdoptionBarChartReport, self).report_config
        config.update(dict(
            group=self.request.GET.get('group_by', ''),
        ))

        return config

    def get_chart(self, rows, columns, x_label, y_label):
        chart = MultiBarChart('Adoption of Practices', x_axis=Axis(x_label), y_axis=Axis(y_label, '%'))

        if self.report_config['group'] == 'domain':
            chart.height = 550
            chart.rotateLabels = -55
            chart.marginBottom = 250
        elif self.report_config['group'] == 'practice':
            chart.height = 700
            chart.rotateLabels = -55
            chart.marginBottom = 400
        else:
            chart.height = 320
            chart.rotateLabels = 0
            chart.marginBottom = 50

        chart.marginLeft = 200
        chart.marginRight = 150
        self._chart_data(chart, columns, rows)
        return [chart]

    def _chart_data(self, chart, columns, rows):
        def p2f(column):
            return float(column['html'].strip('%'))

        def strip_html(text):
            TAG_RE = re.compile(r'<[^>]+>')
            return TAG_RE.sub('', text)

        if self.request.GET.get('group_by', '') == 'domain':
            rows = sorted(rows, key=lambda k: strip_html(k[0]))

        if rows:
            charts = [[], [], []]
            for row in rows:
                group_name = strip_html(row[0])
                for ix, column in enumerate(row[1:]):
                    charts[ix].append({'x': group_name, 'y': p2f(column) / 100.0})

            chart.add_dataset('All', charts[0], "green")
            chart.add_dataset('Some', charts[1], "yellow")
            chart.add_dataset('None', charts[2], "red")

    @property
    def charts(self):
        columns = self.data_provider.columns
        rows = self.rows

        return self.get_chart(rows, columns, '', '')

    @property
    def data_provider(self):
        return AdoptionBarChartReportSqlData(domain=self.domain, config=self.report_config, request_params=self.request_params)


    @property
    def headers(self):
        columns = [c.data_tables_column for c in self.data_provider.columns]
        headers = DataTablesHeader(*columns)
        return headers

    @property
    def rows(self):
        formatter = DataFormatter(TableDataFormat(self.data_provider.columns, no_value=self.data_provider.no_value))
        return formatter.format(self.data_provider.data, keys=self.data_provider.keys, group_by=self.data_provider.group_by)


