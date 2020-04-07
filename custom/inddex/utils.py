from memoized import memoized

from corehq.apps.reports.generic import GenericTabularReport
from corehq.apps.reports.standard import CustomProjectReport, DatespanMixin
from corehq.apps.userreports.reports.util import ReportExport
from custom.inddex.filters import CaseOwnersFilter, DateRangeFilter


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


class MultiTabularReport(DatespanMixin, CustomProjectReport, GenericTabularReport):
    report_template_path = 'inddex/multi_report.html'
    exportable = True
    export_only = False

    @property
    def data_providers(self):
        return []

    @property
    def report_context(self):
        return {
            'reports': [self._get_report_context(dp) for dp in self.data_providers],
            'name': self.name,
            'export_only': self.export_only
        }

    def _get_report_context(self, data_provider):
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

    @property
    def export_table(self):
        prepared_data = [self._format_table_to_export(dp) for dp in self.data_providers]
        export = MultiSheetReportExport(self.name, prepared_data)
        return export.get_table()

    def _format_table_to_export(self, data_provider):
        exported_rows = [[header.html for header in data_provider.headers]]
        exported_rows.extend(data_provider.rows)
        title = data_provider.slug
        return title, exported_rows
