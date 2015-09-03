from StringIO import StringIO

import openpyxl
from openpyxl.formatting import CellIsRule
from openpyxl.styles import PatternFill
from openpyxl.utils import get_column_letter

from corehq.apps.userreports.reports.view import ConfigurableReport


class FormattedSupervisoryReport(ConfigurableReport):
    @property
    def excel_response(self):
        excel_file = super(FormattedSupervisoryReport, self).excel_response

        workbook = openpyxl.load_workbook(excel_file)
        worksheet = workbook.get_active_sheet()

        red = PatternFill(
            start_color='FFEE1111',
            end_color='FFEE1111',
            fill_type='solid',
        )

        max_row = worksheet.max_row
        max_column = get_column_letter(worksheet.max_column)

        # total column
        worksheet.conditional_formatting.add(
            'B2:B%d' % (max_row - 1),
            CellIsRule(
                operator='greaterThan',
                formula=['PERCENTILE($B$2:$B$%d,0.95)' % (worksheet.max_row - 1)],
                fill=red,
            )
        )

        # total row
        worksheet.conditional_formatting.add(
            'C%d:%s%d' % (max_row, max_column, max_row),
            CellIsRule(
                operator='greaterThan',
                formula=['PERCENTILE($C$%d:$%s$%d,0.90)' % (max_row, max_column, max_row)],
                fill=red,
            )
        )

        # body
        worksheet.conditional_formatting.add(
            'C2:%s%d' % (max_column, max_row - 1),
            CellIsRule(
                operator='greaterThan',
                formula=['PERCENTILE($C$2:$%s$%d,0.90)' % (max_column, max_row - 1)],
                fill=red,
            )
        )

        f = StringIO()
        workbook.save(f)
        return f
