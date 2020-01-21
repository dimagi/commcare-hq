from memoized import memoized

from corehq.apps.locations.models import SQLLocation
from corehq.apps.reports.generic import GenericTabularReport
from corehq.apps.reports.standard import CustomProjectReport
from corehq.apps.userreports.reports.util import ReportExport
from custom.inddex.ucr.report_bases.mixins import ReportMixin


class SingleTableReport(ReportMixin, CustomProjectReport):
    title = 'Single Report'
    name = title
    slug = 'single_report'
    report_template_path = 'inddex/tabular_report.html'
    default_rows = 10
    exportable = True

    @property
    def rows(self):
        raise NotImplementedError('\'rows\' must be implemented')

    @property
    def headers(self):
        raise NotImplementedError('\'headers\' must be implemented')

    @property
    def export_format(self):
        return 'xlsx'

    def prepare_table_for_export(self):
        report = [
            [self.name, []]
        ]
        headers = [x.html for x in self.headers]
        rows = self.rows
        report[0][1].append(headers)

        for row in rows:
            report[0][1].append(row)

        return report

    @property
    def export_table(self):
        return self.prepare_table_for_export()

    @property
    @memoized
    def report_context(self):
        if not self.needs_filters:
            return {
                'report': self.get_report_context(),
                'title': self.name
            }
        return {}

    def get_report_context(self):
        if self.needs_filters:
            headers = []
            rows = []
        else:
            rows = self.rows
            headers = self.headers

        context = {
            'report_table': {
                'title': self.name,
                'slug': self.slug,
                'headers': headers,
                'rows': rows,
                'default_rows': self.default_rows,
            }
        }

        return context


class MultiSheetReportExport(ReportExport):

    def __init__(self, title, table_data):
        """
        Allows to export multitabular reports in one xmlns file, different report tables are
        presented as different sheets in document

        :param title: Exported file title
        :param table_data: list of tuples, first element of tuple is sheet title, second is list of rows
        """

        self.title = title
        self.table_data = table_data

    def build_export_data(self):
        sheets = []
        for name, rows in self.table_data:
            sheets.append([name, rows])
        return sheets

    @memoized
    def get_table(self):
        return self.build_export_data()


class MultiTabularReport(ReportMixin, CustomProjectReport, GenericTabularReport):
    title = 'Multi report'
    name = 'Multi Report'
    slug = 'multi_report'
    report_template_path = 'inddex/multi_report.html'
    flush_layout = True
    default_rows = 10
    exportable = True

    @property
    def data_providers(self):
        raise NotImplementedError('\'data_providers\' must implemented')

    @property
    def report_context(self):
        return {
            'reports': [self.get_report_context(dp) for dp in self.data_providers],
            'title': self.title
        }

    @property
    @memoized
    def report_export(self):
        prepared_data = [self.format_table_to_export(dp) for dp in self.data_providers]
        return MultiSheetReportExport(self.title, prepared_data)

    @property
    def export_table(self):
        return self.report_export.get_table()

    def get_report_context(self, data_provider):
        self.data_source = data_provider
        if self.needs_filters:
            headers = []
            rows = []
        else:
            rows = data_provider.rows
            headers = data_provider.headers

        context = dict(
            report_table=dict(
                title=data_provider.title,
                slug=data_provider.slug,
                headers=headers,
                rows=rows
            )
        )

        return context

    def format_table_to_export(self, data_provider):
        exported_rows = [[header.html for header in data_provider.headers]]
        exported_rows.extend(data_provider.rows)
        title = data_provider.slug
        return title, exported_rows
