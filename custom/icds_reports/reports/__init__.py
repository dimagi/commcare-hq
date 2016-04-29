from corehq.apps.reports.filters.fixtures import AsyncLocationFilter
from corehq.apps.reports.filters.select import MonthFilter, YearFilter
from corehq.apps.reports.generic import GenericTabularReport
from corehq.apps.reports.standard import CustomProjectReport, ProjectReportParametersMixin, \
    MonthYearMixin
from dimagi.utils.decorators.memoized import memoized

from corehq.util.dates import get_first_last_days


class IcdsBaseReport(CustomProjectReport, ProjectReportParametersMixin, MonthYearMixin, GenericTabularReport):

    title = 'Block MPR'
    slug = 'icds_report'
    name = 'Block MPR'
    report_template_path = "icds_reports/multi_report.html"
    flush_layout = True
    exportable = True
    is_bootstrap3 = True

    fields = [AsyncLocationFilter, MonthFilter, YearFilter]

    @property
    @memoized
    def rendered_report_title(self):
        return self.title

    @property
    @memoized
    def data_providers(self):
        raise NotImplementedError()

    @property
    def report_config(self):
        start_date, end_date = get_first_last_days(self.year, self.month)
        config = dict(
            location_id=self.request.GET.get('location_id', ''),
            domain=self.domain,
            month=self.month,
            year=self.year,
            start_date=start_date,
            end_date=end_date,
            date_span=self.datespan
        )
        return config

    @property
    def report_context(self):
        context = {
            'reports': [self.get_report_context(dp) for dp in self.data_providers],
            'title': self.title
        }

        return context

    def get_report_context(self, data_provider):
        context = dict(
            report_table=dict(
                title=data_provider.title,
                slug=data_provider.slug,
                headers=data_provider.headers,
                rows=data_provider.rows,
                default_rows=self.default_rows,
                start_at_row=0
            )
        )
        return context

    @property
    def export_table(self):
        reports = [r['report_table'] for r in self.report_context['reports']]
        return [self._export_table(r['title'], r['headers'], r['rows']) for r in reports]

    def _export_table(self, export_sheet_name, headers, formatted_rows, total_row=None):
        def _unformat_row(row):
            return [col.get("sort_key", col) if isinstance(col, dict) else col for col in row]
        if headers:
            table = headers.as_export_table
        else:
            table = [[''] * len(formatted_rows[0])]

        replace = ''

        # make headers and subheaders consistent
        for k, v in enumerate(table[0]):
            if v != ' ':
                replace = v
            else:
                table[0][k] = replace

        rows = [_unformat_row(row) for row in formatted_rows]
        table.extend(rows)
        if total_row:
            table.append(_unformat_row(total_row))

        return [export_sheet_name, table]
