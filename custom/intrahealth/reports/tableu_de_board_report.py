from corehq.apps.reports.datatables import DataTablesHeader
from corehq.apps.reports.filters.dates import DatespanFilter
from corehq.apps.reports.filters.fixtures import AsyncLocationFilter
from corehq.apps.reports.graph_models import MultiBarChart, Axis
from corehq.apps.reports.sqlreport import DataFormatter, TableDataFormat, calculate_total_row
from corehq.apps.reports.standard import CustomProjectReport, ProjectReportParametersMixin, DatespanMixin
from dimagi.utils.decorators.memoized import memoized
from custom.intrahealth.sqldata import *


class MultiReport(CustomProjectReport, ProjectReportParametersMixin, DatespanMixin):

    title = ''
    report_template_path = "intrahealth/multi_report.html"
    flush_layout = True
    no_value = {'sort_key': 0, 'html': 0}

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

    def get_report_context(self, data_provider):
        headers = DataTablesHeader(*[c.data_tables_column for c in data_provider.columns])

        if self.needs_filters:
            rows = []
            charts = []
            total_row = []
        else:
            formatter = DataFormatter(TableDataFormat(data_provider.columns, no_value=self.no_value))
            rows = list(formatter.format(data_provider.data, keys=data_provider.keys, group_by=data_provider.group_by))
            charts = list(self.get_chart(
                rows,
                data_provider.columns,
                x_label=data_provider.chart_x_label,
                y_label=data_provider.chart_y_label,
                has_total_column=False
            ))

            total_row = list(calculate_total_row(rows))
            if total_row:
                total_row[0] = 'Total'

        context = dict(
            report_table=dict(
                title=data_provider.title,
                headers=headers,
                rows=rows,
                total_row=total_row,
                default_rows=self.default_rows,
                datatables=True
            ),
            charts=charts,
            chart_span=12
        )

        return context

    def get_chart(self, rows, columns, x_label, y_label, has_total_column=False):

        end = len(columns)
        if has_total_column:
            end -= 1
        categories = [c.data_tables_column.html for c in columns[1:end]]
        chart = MultiBarChart('', x_axis=Axis(x_label), y_axis=Axis(y_label, ' ,d'))
        chart.rotateLabels = -45
        chart.marginBottom = 120
        self._chart_data(chart, categories, rows)
        return [chart]

    def _chart_data(self, chart, series, data, start_index=1, x_fn=None, y_fn=None):
        xfn = x_fn or (lambda x: x['html'])
        yfn = y_fn or (lambda y: y['sort_key'])
        for i, s in enumerate(series):
            chart.add_dataset(s, [{'x': xfn(d[0]), 'y': yfn(d[start_index + i])} for d in data])

class TableuDeBoardReport(MultiReport):
    title = "TABLEU DE BORD INDICATEURS - RAPPORT IPM"
    fields = [DatespanFilter, AsyncLocationFilter]
    name = "TABLEU DE BORD INDICATEURS - RAPPORT IPM"
    slug = 'tableu_de_board'
    default_rows = 10

    @property
    def locations_id(self):
        return AsyncLocationFilter.get_value(self.request, self.domain)

    @property
    def report_config(self):
        config = dict(
            domain=self.domain,
            datespan=self.datespan,
            locations_id=self.locations_id,
        )
        return config

    @property
    @memoized
    def data_providers(self):
        config = self.report_config
        return [
            ConventureData(config=config),
            DispDesProducts(config=config),
        ]
