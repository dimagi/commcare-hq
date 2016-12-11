"""
the data models here are modeled after openpyxl data models
but are greatly reduced to expose only the values needed

"""
from collections import namedtuple


class Workbook(namedtuple('Workbook', ['worksheets'])):

    def get_sheet_by_name(self, name):
        for worksheet in self.worksheets:
            if worksheet.title == name:
                return worksheet
        raise ValueError("Worksheet {0} does not exist.".format(name))


class Worksheet(namedtuple('Worksheet', ['title', 'max_row', 'iter_rows'])):
    pass


class Cell(namedtuple('Cell', ['value'])):
    pass
