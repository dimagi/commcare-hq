from corehq.apps.reports.datatables import DataTablesHeader
from corehq.apps.reports.graph_models import MultiBarChart, Axis
from corehq.apps.reports.sqlreport import calculate_total_row, TableDataFormat, DataFormatter
from corehq.apps.style.decorators import use_nvd3_v3
from dimagi.utils.decorators.memoized import memoized
from corehq.apps.reports.standard import DatespanMixin, CustomProjectReport, ProjectReportParametersMixin
from .filters import AgeFilter, GenderFilter, GroupUserFilter, GroupFilter, ALL_CVSU_GROUP
from .sqldata import (ChildProtectionData, ChildrenInHouseholdData,
                      ChildProtectionDataTrend, ChildrenInHouseholdDataTrend,
                      CVSUActivityData, CVSUActivityDataTrend,
                      CVSUIncidentResolutionData, CVSUIncidentResolutionDataTrend,
                      CVSUServicesData, CVSUServicesDataTrend)


class MultiReportPage(CustomProjectReport, ProjectReportParametersMixin, DatespanMixin):
    """
    Report class that supports having multiple 'reports' shown at a time.

    i.e. multiple sections of _graph and report table_

    Each section is represented by a 'data provider' class.
    """
    title = ''
    report_template_path = "cvsu/multi_report.html"
    flush_layout = True

    @use_nvd3_v3
    def decorator_dispatcher(self, request, *args, **kwargs):
        return super(MultiReportPage, self).decorator_dispatcher(request, *args, **kwargs)

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
                has_total_column=data_provider.has_total_column
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

    @property
    def export_table(self):
        reports = [r['report_table'] for r in self.report_context['reports']]
        return [self._export_table(r['title'], r['headers'], r['rows'], total_row=r['total_row']) for r in reports]

    def _export_table(self, export_sheet_name, headers, formatted_rows, total_row=None):
        def _unformat_row(row):
            return [col.get("sort_key", col) if isinstance(col, dict) else col for col in row]

        table = headers.as_export_table
        rows = [_unformat_row(row) for row in formatted_rows]
        table.extend(rows)
        if total_row:
            table.append(_unformat_row(total_row))

        return [export_sheet_name, table]

    def get_chart(self, rows, columns, x_label, y_label, has_total_column=False):
        """
        Get a MultiBarChart model for the given set of rows and columns.
        :param rows: 2D list of report data. Assumes index 0 of each row is the row label
        :param columns: list of DatabaseColumn objects
        """
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


class CVSUReport(MultiReportPage):
    no_value = {'sort_key': 0, 'html': u'\u2014'}
    default_rows = 100
    datespan_default_days = 30
    printable = True
    exportable = True
    filter_group_name = 'All CVSUs'

    @property
    def location(self):
        cvsu = 'All CVSU'
        group = 'All Districts'

        if self.group_id == ALL_CVSU_GROUP:
            return group

        if self.individual:
            cvsu = self.CommCareUser.get_by_user_id(self.individual).raw_username

        if self.group and self.group_id != ALL_CVSU_GROUP:
            group = self.group.name

        return '%s, %s' % (cvsu, group)

    @property
    def daterange(self):
        format = "%d %b %Y"
        st = self.datespan.startdate.strftime(format)
        en = self.datespan.enddate.strftime(format)
        return "%s to %s" % (st, en)

    @property
    def subtitle(self):
        if self.needs_filters:
            return dict(subtitle1='', subtitle2='')

        return dict(subtitle1="Date range: %s" % self.daterange,
                    subtitle2="CVSU Location: %s" % self.location)

    @property
    def age(self):
        return AgeFilter.get_value(self.request, self.domain)

    @property
    def age_display(self):
        return AgeFilter.age_display_map[self.age] if self.age else 'All'

    @property
    def gender(self):
        return GenderFilter.get_value(self.request, self.domain)

    @property
    def individual(self):
        return GroupUserFilter.get_value(self.request, self.domain).get('cvsu')

    @property
    def report_context(self):
        context = super(CVSUReport, self).report_context
        context.update(self.subtitle)
        return context


class ChildProtectionReport(CVSUReport):
    title = 'CVSU CHILD PROTECTION AND GENDER BASED VIOLENCE LOCATION REPORT'
    name = "Location report"
    slug = "child_protection_location"
    fields = (DatespanMixin.datespan_field, "custom.apps.cvsu.filters.GroupFilter",
              "custom.apps.cvsu.filters.AgeFilter", "custom.apps.cvsu.filters.GenderFilter")

    @property
    def group_id(self):
        return GroupFilter.get_value(self.request, self.domain)

    @property
    def subtitle(self):
        if self.needs_filters:
            return dict(subtitle='')

        gender = self.gender or 'All'

        subtitle = super(ChildProtectionReport, self).subtitle
        subtitle.update({
            'subtitle2': "%s, Survivor age: %s, Survivor gender: %s" % (subtitle['subtitle2'], self.age_display, gender)
        })
        return subtitle

    @property
    def report_config(self):
        config = dict(
            domain=self.domain,
            datespan=self.datespan,
            age=self.age,
            gender=self.gender,
            group_id=self.group_id,
            user_id=self.individual
        )
        return config

    @property
    @memoized
    def data_providers(self):
        config = self.report_config
        return [
            ChildProtectionData(config=config),
            ChildrenInHouseholdData(config=config)
        ]


class ChildProtectionReportTrend(ChildProtectionReport):
    title = 'CVSU CHILD PROTECTION AND GENDER BASED VIOLENCE TREND REPORT'
    name = "Trend report"
    slug = "child_protection_trend"
    fields = (DatespanMixin.datespan_field, "custom.apps.cvsu.filters.GroupUserFilter",
              "custom.apps.cvsu.filters.AgeFilter", "custom.apps.cvsu.filters.GenderFilter")

    @property
    def group_id(self):
        return GroupUserFilter.get_value(self.request, self.domain).get('district')

    @property
    @memoized
    def data_providers(self):
        config = self.report_config
        return [
            ChildProtectionDataTrend(config=config),
            ChildrenInHouseholdDataTrend(config=config)
        ]


class CVSUPerformanceReport(CVSUReport):
    title = 'CVSU PERFORMANCE EVALUATION LOCATION REPORT'
    name = "Location report"
    slug = "cvsu_performance_location"
    fields = (DatespanMixin.datespan_field, "custom.apps.cvsu.filters.GroupFilter")

    @property
    def group_id(self):
        return GroupFilter.get_value(self.request, self.domain)

    @property
    def report_config(self):
        config = dict(
            domain=self.domain,
            datespan=self.datespan,
            group_id=self.group_id,
            user_id=self.individual
        )
        return config

    @property
    @memoized
    def data_providers(self):
        config = self.report_config
        return [
            CVSUActivityData(config=config),
            CVSUServicesData(config=config),
            CVSUIncidentResolutionData(config=config)
        ]


class CVSUPerformanceReportTrend(CVSUPerformanceReport):
    title = 'CVSU PERFORMANCE EVALUATION TREND REPORT'
    name = "Trend report"
    slug = "cvsu_performance_trend"
    fields = (DatespanMixin.datespan_field, "custom.apps.cvsu.filters.GroupUserFilter")

    @property
    def group_id(self):
        return GroupUserFilter.get_value(self.request, self.domain).get('district')

    @property
    @memoized
    def data_providers(self):
        config = self.report_config
        return [
            CVSUActivityDataTrend(config=config),
            CVSUServicesDataTrend(config=config),
            CVSUIncidentResolutionDataTrend(config=config)
        ]
