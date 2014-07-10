from corehq.apps.locations.models import Location
from corehq.apps.reports.filters.dates import DatespanFilter
from corehq.apps.reports.filters.fixtures import AsyncLocationFilter
from corehq.apps.reports.graph_models import MultiBarChart, Axis
from corehq.apps.reports.sqlreport import calculate_total_row
from corehq.apps.reports.standard import CustomProjectReport, ProjectReportParametersMixin, DatespanMixin
from dimagi.utils.decorators.memoized import memoized
from custom.intrahealth.filters import LocationFilter
from custom.intrahealth.reports import IntraHealtMixin
from custom.intrahealth.sqldata import *


class MultiReport(CustomProjectReport, IntraHealtMixin, ProjectReportParametersMixin, DatespanMixin):

    title = ''
    report_template_path = "intrahealth/multi_report.html"
    flush_layout = True

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

        total_row = []
        charts = []
        if self.needs_filters:
            headers = []
            rows = []
        else:
            if isinstance(data_provider, ConventureData):
                columns = [c.data_tables_column for c in data_provider.columns]
                headers = DataTablesHeader(*columns)
                rows = data_provider.rows
            elif isinstance(data_provider, DispDesProducts):
                headers = data_provider.headers
                rows = data_provider.rows
            else:
                self.model = data_provider
                headers = self.headers
                rows = self.rows
            if data_provider.show_total:
                if data_provider.custom_total_calculate:
                    total_row = data_provider.calculate_total_row(rows)
                else:
                    total_row = list(calculate_total_row(rows))
                    if total_row:
                        total_row[0] = 'Total'

            if data_provider.show_charts:
                charts = list(self.get_chart(
                    total_row,
                    headers,
                    x_label=data_provider.chart_x_label,
                    y_label=data_provider.chart_y_label,
                    has_total_column=False
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

    def get_chart(self, rows, columns, x_label, y_label, has_total_column=False):

        end = len(columns)
        if has_total_column:
            end -= 1
        categories = [c.html for c in columns.header[1:end]]
        chart = MultiBarChart('', x_axis=Axis(x_label), y_axis=Axis(y_label, ' ,d'))
        chart.rotateLabels = -45
        chart.marginBottom = 120
        self._chart_data(chart, categories, rows)
        return [chart]

    def _chart_data(self, chart, series, data):
        if data:
            charts = []
            for i, s in enumerate(series):
                charts.append({'x': s, 'y': data[i+1]})
            chart.add_dataset('products', charts)

class TableuDeBoardReport(MultiReport):
    title = "Tableu De Bord"
    fields = [DatespanFilter, LocationFilter]
    name = "Tableu De Bord"
    slug = 'tableu_de_board'
    default_rows = 10

    @property
    @memoized
    def data_providers(self):
        config = self.report_config
        if 'district_id' in config:
            return [
                ConventureData(config=config),
                ConsommationData(config=config),
                TauxConsommationData(config=config),
                NombreData(config=config)
            ]
        else:
            return [
                ConventureData(config=config),
                DispDesProducts(config=config),
                ConsommationData(config=config),
                TauxConsommationData(config=config),
                NombreData(config=config)
            ]
