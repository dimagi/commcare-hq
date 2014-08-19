
from corehq.apps.reports.datatables import DataTablesHeader, DataTablesColumn
from corehq.apps.reports.generic import GenericTabularReport, GetParamsMixin
from corehq.apps.reports.graph_models import MultiBarChart, Axis
from corehq.apps.reports.sqlreport import TableDataFormat
from corehq.apps.reports.standard import CustomProjectReport
from custom.care_pathways.fields import GeographyFilter, GenderFilter, GroupLeadershipFilter, CBTNameFilter, GroupByFilter, PPTYearFilter, TypeFilter, ScheduleFilter, \
    DisaggregateByFilter
from custom.care_pathways.reports.adoption_bar_char_report import AdoptionBarChartReport
from custom.care_pathways.sqldata import AdoptionDisaggregatedSqlData
from custom.care_pathways.utils import get_domain_configuration, CareDataFormatter, _chunks


class AdoptionDisaggregatedReport(GetParamsMixin, GenericTabularReport, CustomProjectReport):
    name = 'Adoption Disaggregated'
    slug = 'adoption_disaggregated'
    report_title = 'Adoption Disaggregated'
    report_template_path = 'care_pathways/report.html'
    default_rows = 100

    @property
    def fields(self):
        filters = [GeographyFilter,
              GroupByFilter,
              PPTYearFilter,
              TypeFilter,
              GenderFilter,
              GroupLeadershipFilter,
              CBTNameFilter,
              ]
        if self.domain == 'pathways-india-mis':
            filters.append(ScheduleFilter)
        filters.append(DisaggregateByFilter)
        return filters

    @property
    def report_config(self):

        config = dict(
            domain=self.domain,
            ppt_year=self.request.GET.get('year', ''),
            value_chain=self.request.GET.get('type_value_chain', ''),
            domains=tuple(self.request.GET.getlist('type_domain', [])),
            practices=tuple(self.request.GET.getlist('type_practice', [])),
            group=self.request.GET.get('group_by', ''),
            owner_id=self.request.GET.get('cbt_name', ''),
            gender=self.request.GET.get('gender', ''),
            group_leadership=self.request.GET.get('group_leadership', ''),
            schedule=self.request.GET.get('farmer_social_category', ''),
            disaggregate_by=self.request.GET.get('disaggregate_by', '')
        )
        hierarchy_config = get_domain_configuration(self.domain)['geography_hierarchy']
        for k, v in sorted(hierarchy_config.iteritems(), reverse=True):
            req_prop = 'geography_%s' % v['prop']
            if self.request.GET.getlist(req_prop, []):
                config.update({k: tuple(self.request.GET.getlist(req_prop, []))})
                break

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
        chunks = _chunks(list(rows), self.chunk_size+1)
        charts = []
        for chunk in chunks:

            chart = MultiBarChart(chunk[0][0], x_axis=Axis(x_label), y_axis=Axis(y_label))
            chart.forceY = [0, 100]
            chart.height = 300
            chart.rotateLabels = 0
            chart.marginBottom = 80
            chart.marginLeft = 100
            self._chart_data(chart, chunk[1:])
            charts.append(chart)
        return charts

    def _chart_data(self, chart, rows):
        def p2f(column):
            return float(column['html'].strip('%'))

        if rows:
            charts = [[], [], []]
            for row in rows:
                group_name = row[0]
                for ix, column in enumerate(row[1:]):
                    charts[ix].append({'x': group_name, 'y': column})

            chart.add_dataset('All', charts[0], "blue")
            chart.add_dataset('Some', charts[1], "green")
            chart.add_dataset('None', charts[2], "red")

    @property
    def charts(self):
        rows = self.rows
        return self.get_chart(rows, '', '')