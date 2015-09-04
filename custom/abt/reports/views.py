import json
from StringIO import StringIO

from django.http import HttpResponse

import openpyxl
from openpyxl.formatting import CellIsRule
from openpyxl.styles import PatternFill
from openpyxl.utils import get_column_letter

from corehq.apps.userreports.reports.view import ConfigurableReport


class FormattedSupervisoryReport(ConfigurableReport):

    @property
    def export_table(self):
        data = super(FormattedSupervisoryReport, self).export_table
        table = data[0][1]
        for row in range(1, len(table) - 1):
            for column in range(2, len(table[row])):
                if table[row][column] == 0:
                    table[row][column] = ''
        return data

    @property
    def excel_response(self):
        unformatted_excel_file = super(FormattedSupervisoryReport, self).excel_response

        workbook = openpyxl.load_workbook(unformatted_excel_file)
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

    @property
    def email_response(self):
        return HttpResponse(json.dumps({
            'report': '',
        }))
