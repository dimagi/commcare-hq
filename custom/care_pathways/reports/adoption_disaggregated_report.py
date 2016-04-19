from corehq.apps.reports.datatables import DataTablesHeader, DataTablesColumn
from corehq.apps.reports.graph_models import MultiBarChart, Axis
from corehq.apps.reports.sqlreport import TableDataFormat
from custom.care_pathways.reports import CareBaseReport
from custom.care_pathways.filters import GeographyFilter, GenderFilter, GroupLeadershipFilter, CBTNameFilter, \
    GroupByFilter, PPTYearFilter, ScheduleFilter, DisaggregateByFilter, TypeFilter, MalawiPPTYearFilter, \
    RealOrTestFilter
from custom.care_pathways.sqldata import AdoptionDisaggregatedSqlData
from custom.care_pathways.utils import CareDataFormatter, _chunks


class AdoptionDisaggregatedReport(CareBaseReport):
    name = 'Adoption Disaggregated'
    slug = 'adoption_disaggregated'
    report_title = 'Adoption Disaggregated'
    report_template_path = 'care_pathways/adoption_disaggregated_report.html'
    default_rows = 100

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
        filters.append(DisaggregateByFilter)
        return filters

    @property
    def report_config(self):
        config = super(AdoptionDisaggregatedReport, self).report_config
        config.update(dict(
            group=self.request.GET.get('group_by', ''),
            disaggregate_by=self.request.GET.get('disaggregate_by', '')
        ))

        self.chunk_size = 1 if (config['gender'] or config['group_leadership']) else 3
        return config

    @property
    def report_context(self):
        context = super(AdoptionDisaggregatedReport, self).report_context
        context.update({'chunk_size': self.chunk_size+1})
        return context

    @property
    def data_provider(self):
        return AdoptionDisaggregatedSqlData(domain=self.domain, config=self.report_config, request_params=self.request_params)


    @property
    def headers(self):
        columns = [DataTablesColumn(c.header, sortable=False) for c in self.data_provider.columns]
        headers = DataTablesHeader(*columns)
        return headers

    @property
    def rows(self):
        formatter = CareDataFormatter(TableDataFormat(self.data_provider.columns, no_value=self.data_provider.no_value))
        return formatter.format(self.data_provider.data, keys=self.data_provider.keys,
                                group_by=self.data_provider.group_by, domain=self.domain, chunk_size=self.chunk_size)
    
    def get_chart(self, rows, x_label, y_label):
        chunks = _chunks(list(rows), self.chunk_size + 1)
        charts = []
        if self.request.GET.get('group_by', '') == 'domain':
            chunks = sorted(chunks, key=lambda k: k[0][0])
        for chunk in chunks:
            chart = MultiBarChart(chunk[0][0], x_axis=Axis(x_label), y_axis=Axis(y_label, '.0%'))
            chart.height = 300
            chart.rotateLabels = 0
            chart.marginBottom = 80
            chart.marginLeft = 100
            self._chart_data(chart, chunk[1:])
            charts.append(chart)
        return charts

    def _chart_data(self, chart, rows):
        def p2f(column):
            return float(column['html'].strip('%')) / 100.0

        if rows:
            charts = [[], [], []]
            for row in rows:
                group_name = row[0]
                total = sum(row[1:])
                total = float(total) if total else 1.0
                for ix, column in enumerate(row[1:]):
                    charts[ix].append({'x': group_name, 'y': float(column) / total})

            chart.add_dataset('None', charts[0], "red")
            chart.add_dataset('Some', charts[1], "yellow")
            chart.add_dataset('All', charts[2], "green")

    @property
    def charts(self):
        rows = self.rows
        return self.get_chart(rows, '', '')
