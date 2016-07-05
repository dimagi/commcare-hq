from corehq.apps.reports.filters.dates import DatespanFilter
from corehq.apps.reports.graph_models import MultiBarChart, Axis
from corehq.apps.reports.standard import CustomProjectReport, ProjectReportParametersMixin, DatespanMixin
from corehq.apps.style.decorators import use_nvd3
from custom.intrahealth.filters import LocationFilter
from custom.intrahealth.reports import IntraHealtMixin
from custom.intrahealth.sqldata import *


class MultiReport(CustomProjectReport, IntraHealtMixin, ProjectReportParametersMixin, DatespanMixin):

    title = ''
    report_template_path = "intrahealth/multi_report.html"
    flush_layout = True
    export_format_override = 'csv'

    @use_nvd3
    def decorator_dispatcher(self, request, *args, **kwargs):
        super(MultiReport, self).decorator_dispatcher(request, *args, **kwargs)

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
        self.data_source = data_provider
        if self.needs_filters:
            headers = []
            rows = []
        else:
            if isinstance(data_provider, (ConventureData, RecapPassageData, DureeData, PPSAvecDonnees,
                                          RecouvrementDesCouts)):
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
            if isinstance(data_provider, TauxDeRuptures):
                headers.add_column(DataTablesColumn("Au moins 1 produit"))
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


class TableuDeBoardReport(MultiReport):
    title = "Tableau De Bord"
    fields = [DatespanFilter, LocationFilter]
    name = "Tableau De Bord"
    slug = 'tableu_de_board'
    default_rows = 10
    exportable = True

    @property
    @memoized
    def data_providers(self):
        config = self.report_config
        locations = []

        if 'region_id' in config:
            locations = tuple(SQLLocation.objects.get(
                location_id=config['region_id']
            ).archived_descendants().values_list('location_id', flat=True))
        elif 'district_id' in config:
            locations = tuple(SQLLocation.objects.get(
                location_id=config['district_id']
            ).archived_descendants().values_list('location_id', flat=True))

        if locations:
            config.update({'archived_locations': locations})

        if 'district_id' in config:
            return [
                ConventureData(config=config),
                PPSAvecDonnees(config=config),
                TauxDeRuptures(config=config),
                ConsommationData(config=config),
                TauxConsommationData(config=config),
                NombreData(config=config),
                GestionDeLIPMTauxDeRuptures(config=config),
                RecouvrementDesCouts(config=config)
            ]
        else:
            return [
                ConventureData(config=config),
                PPSAvecDonnees(config=config),
                DispDesProducts(config=config),
                TauxDeRuptures(config=config),
                ConsommationData(config=config),
                TauxConsommationData(config=config),
                NombreData(config=config),
                GestionDeLIPMTauxDeRuptures(config=config),
                DureeData(config=config),
                RecouvrementDesCouts(config=config)
            ]
