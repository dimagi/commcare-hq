from memoized import memoized

from corehq.apps.reports.datatables import DataTablesHeader, DataTablesColumn
from corehq.apps.userreports.reports.util import ReportExport
from corehq.apps.userreports.reports.view import CustomConfigurableReport
from custom.inddex.utils import MultiSheetReportExport


class ProcessDataReport(CustomConfigurableReport):
    # template_name = 'reports/base_template.html' TODO: Need template that prevents showing tables

    @property
    def table_data(self):
        # TODO: instead of mock data retun proper calculations
        return [("Raport 1", [['head 1', 'head2'], ['row1','row11']]),
                ("Raport 2",  [['head 2', 'head2'], ['row2','row22']]),
                ("Raport 3", ['a'])]

    @property
    @memoized
    def report_export(self):
        return MultiSheetReportExport('Crazy title', self.table_data)

