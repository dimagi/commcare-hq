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

        def percentile_fill(start_column, start_row, end_column, end_row,
                            percentile, fill):
            format_range = {
                'start_column': start_column,
                'start_row': start_row,
                'end_column': end_column,
                'end_row': end_row,
            }
            worksheet.conditional_formatting.add(
                "%(start_column)s%(start_row)d:%(end_column)s%(end_row)d" % format_range,
                CellIsRule(
                    operator='greaterThan',
                    formula=[(
                        'PERCENTILE($%(start_column)s$%(start_row)d:'
                        '$%(end_column)s$%(end_row)d,{})'
                    ).format(percentile) % format_range],
                    fill=fill
                )
            )

        # total column
        percentile_fill('B', 2, 'B', max_row - 1, 0.95, red)

        # total row
        percentile_fill('C', max_row, max_column, max_row, 0.90, red)

        # body
        percentile_fill('C', 2, max_column, max_row - 1, 0.90, red)

        f = StringIO()
        workbook.save(f)
        return f

    @property
    def email_response(self):
        return HttpResponse(json.dumps({
            'report': '',
        }))
