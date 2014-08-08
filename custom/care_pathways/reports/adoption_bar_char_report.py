import urllib
from django.utils import html
from corehq.apps.reports.datatables import DataTablesHeader
from corehq.apps.reports.generic import GenericTabularReport
from corehq.apps.reports.graph_models import MultiBarChart, LineChart, Axis
from corehq.apps.reports.standard import DatespanMixin, CustomProjectReport
from custom.care_pathways.fields import GeographyFilter, GenderFilter, GroupLeadershipFilter, CBTNameFilter, \
    ScheduleCasteFilter, ScheduleTribeFilter, GroupByFilter, PPTYearFilter, TypeFilter
from custom.care_pathways.sqldata import AdoptionBarChartReportSqlData
from custom.care_pathways.utils import get_domain_configuration, get_domains, get_mapping, get_pracices, is_domain, is_mapping, is_practice


class AdoptionBarChartReport(DatespanMixin, GenericTabularReport, CustomProjectReport):
    name = 'Adoption Bar Chart'
    slug = 'adoption_bar_chart'
    report_title = 'Adoption Bar Chart'

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
            filters.extend([ScheduleCasteFilter, ScheduleTribeFilter])

        return filters

    @property
    def report_config(self):
        config = dict(
            domain=self.domain,
            year=self.request.GET.get('year', ''),
            value_chain=self.request.GET.get('type_value_chain', ''),
            domains=tuple(self.request.GET.getlist('type_domain', [])),
            practices=tuple(self.request.GET.getlist('type_practice', []))
        )
        return config

    def get_chart(self, rows, columns, x_label, y_label):
        chart = MultiBarChart('Adoption of Practices', x_axis=Axis(x_label), y_axis=Axis(y_label))
        chart.marginBottom = 120
        self._chart_data(chart, columns, rows)
        return [chart]

    def _chart_data(self, chart, columns, rows):
        if rows:
            charts = [[], [], []]
            for row in rows:
                group_name = self.get_group_name(row[0])
                for ix, column in enumerate(row[1:]):
                    charts[ix].append({'x': group_name, 'y': column})

            chart.add_dataset('All', charts[0], "blue")
            chart.add_dataset('None', charts[1], "red")
            chart.add_dataset('Some', charts[2], "green")

    @property
    def charts(self):
        columns = self.data_provider.columns
        rows = self.data_provider.rows

        return self.get_chart(rows, columns, '', '')

    @property
    def data_provider(self):
        return AdoptionBarChartReportSqlData(domain=self.domain, config=self.report_config)

    @property
    def configuration(self):
        return get_domain_configuration(self.domain)

    @property
    def headers(self):
        columns = [c.data_tables_column for c in self.data_provider.columns]
        headers = DataTablesHeader(*columns)
        return headers

    @property
    def rows(self):
        for row in self.data_provider.rows:
            row[0] = self.get_group_link(row[0])
            yield row

    def get_group_link(self, name):
        params = self.request_params
        display_name = self.get_group_name(name)

        #set url params based on group name
        if is_mapping(name, self.domain):
            params['type_value_chain'] = name

        if is_domain(name, self.domain):
            params['type_domain'] = name

        #TODO practices should probably redirect url to some other report

        url = html.escape(AdoptionBarChartReport.get_url(*[self.domain]) + "?" + urllib.urlencode(params))
        return html.mark_safe("<a class='ajax_dialog' href='%s' target='_blank'>%s</a>" % (url, display_name))

    def get_group_name(self, group_name):
        if is_mapping(group_name, self.domain):
            return next((item for item in get_mapping(self.domain) if item['val'] == group_name), None)['text']

        if is_domain(group_name, self.domain):
            return next((item for item in get_domains(self.domain) if item['val'] == group_name), None)['text']

        if is_practice(group_name, self.domain):
            return next((item for item in get_pracices(self.domain) if item['val'] == group_name), None)['text']

        return group_name
