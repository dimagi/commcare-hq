from __future__ import absolute_import
from dateutil.relativedelta import relativedelta

from corehq.apps.reports.generic import GenericTabularReport
from corehq.apps.reports.standard import CustomProjectReport, ProjectReportParametersMixin, \
    MonthYearMixin
from dimagi.utils.decorators.memoized import memoized

from corehq.util.dates import get_first_last_days


class IcdsBaseReport(CustomProjectReport, ProjectReportParametersMixin, MonthYearMixin, GenericTabularReport):

    report_template_path = "icds_reports/multi_report.html"
    flush_layout = True
    exportable = True

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
        month_before = start_date - relativedelta(months=1)
        new_start_date = month_before.replace(day=21)
        new_end_date = start_date.replace(day=20)
        self.datespan.startdate = new_start_date
        self.datespan.enddate = new_end_date
        state = self.request.GET.get('icds_state_id', None)
        district = self.request.GET.get('icds_district_id', None)
        block = self.request.GET.get('icds_state_id', None)
        location_id = self.request.GET.get('location_id', None)
        if state:
            location_id = state
        if district:
            location_id = district
        if block:
            location_id = block
        config = dict(
            location_id=location_id,
            domain=self.domain,
            month=self.month,
            year=self.year,
            start_date=new_start_date,
            end_date=new_end_date,
            date_span=self.datespan
        )
        return config

    @property
    def report_context(self):
        context = {
            'reports': [self.get_report_context(dp) for dp in self.data_providers],
            'title': self.title,
        }

        return context

    def get_report_context(self, data_provider):
        context = dict(
            has_sections=data_provider.has_sections,
            posttitle=data_provider.posttitle,
            report_table=dict(
                title=data_provider.title,
                slug=data_provider.slug,
                headers=data_provider.headers,
                rows=data_provider.rows,
                subtitle=data_provider.subtitle,
                default_rows=self.default_rows,
                start_at_row=0,
            )
        )
        return context

    @property
    def export_table(self):
        reports = []
        for report in self.report_context['reports']:
            if report['has_sections']:
                for section in report['report_table']['rows']:
                    reports.append(self._export_table(section['title'], [], section['headers'], section['rows']))
            else:
                reports.append(
                    self._export_table(
                        report['report_table']['title'],
                        report['report_table']['subtitle'],
                        report['report_table']['headers'],
                        report['report_table']['rows'])
                )

        return reports

    def _export_table(self, export_sheet_name, subtitle, headers, formatted_rows, total_row=None):
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
        for sub in reversed(subtitle):
            table.insert(0, [sub])
        table.insert(0, [export_sheet_name])
        return [export_sheet_name, table]


from custom.icds_reports.reports.reports import MPRReport, ASRReport, TableauReport, DashboardReport


CUSTOM_REPORTS = (
    ('BLOCK REPORTS', (
        MPRReport,
        ASRReport
    )),
    ('CUSTOM REPORTS', (
        TableauReport,
        DashboardReport,
    )),
)
