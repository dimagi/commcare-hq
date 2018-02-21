from __future__ import absolute_import
from __future__ import division
from corehq.apps.reports.graph_models import MultiBarChart, Axis
from custom.care_pathways.reports import CareBaseReport
from custom.care_pathways.filters import TableCardGroupByFilter, TableCardTypeFilter
from dimagi.utils.decorators.memoized import memoized
from custom.care_pathways.sqldata import TableCardReportIndividualPercentSqlData, TableCardReportGrouppedPercentSqlData, TableCardSqlData


class TableCardReport(CareBaseReport):
    name = 'Table Report Card'
    slug = 'table_card_report'
    report_title = 'Table Report Card'
    report_template_path = "care_pathways/table_card_report.html"

    @property
    @memoized
    def data_providers(self):
        config = self.report_config
        config.update(dict(
            group='practice',
            table_card_group_by= self.request.GET.get('group_by', ''),
        ))

        return [TableCardSqlData(self.domain, config, self.request_params),
                TableCardReportGrouppedPercentSqlData(self.domain, config, self.request_params),
                TableCardReportIndividualPercentSqlData(self.domain, config, self.request_params)]

    @property
    def report_context(self):
        rows = []
        if not self.needs_filters:
            rows = self.data_providers[0].data

        context = {
            'reports': [self.get_report_context(dp, rows) for dp in self.data_providers[1:]],
            'title': self.report_title
        }

        return context

    def get_report_context(self, data_provider, rows):
        total_row = []
        headers = []
        charts = []

        if rows:
            headers = data_provider.headers(rows)
            rows = list(data_provider.format_rows(rows))

            if data_provider.show_total:
                total_row = data_provider.calculate_total_row(headers, rows)

            if data_provider.show_charts:
                charts = list(self.get_chart(
                    rows,
                    headers,
                    x_label=data_provider.chart_x_label,
                    y_label=data_provider.chart_y_label
                ))
        context = dict(
            report_table=dict(
                title=data_provider.title,
                slug=data_provider.slug,
                headers=headers,
                rows=rows,
                total_row=total_row,
                default_rows=self.default_rows,
                datatables=data_provider.datatables,
                start_at_row=0,
                fix_column=data_provider.fix_left_col
            ),
            charts=charts,
            chart_span=12
        )

        return context

    @property
    def fields(self):
        filters = super(TableCardReport, self).fields
        filters.append(TableCardTypeFilter)
        filters.append(TableCardGroupByFilter)
        return filters

    def get_chart(self, rows, columns, x_label, y_label):
        chart = MultiBarChart('% of Groups Receiving Grades', x_axis=Axis(x_label), y_axis=Axis(y_label, '.0%'))
        chart.height = 400
        chart.rotateLabels = -60
        chart.marginBottom = 90
        chart.marginLeft = 100
        self._chart_data(chart, columns, rows)
        return [chart]

    def _chart_data(self, chart, columns, rows):
        def p2f(column):
            return float(column.strip('%')) / 100

        if rows:
            charts = [[], [], [], []]
            flat_columns = []
            for group_column in columns.header[1:]:
                for c in group_column.columns:
                    flat_columns.append(c.html)

            for idx, row in enumerate(rows):
                for ix, column in enumerate(row[1:]):
                    group_name = flat_columns[ix]
                    charts[idx].append({'x': group_name, 'y': p2f(column)})

            chart.add_dataset('A', charts[0], "green")
            chart.add_dataset('B', charts[1], "orange")
            chart.add_dataset('C', charts[2], "yellow")
            chart.add_dataset('D', charts[3], "red")
