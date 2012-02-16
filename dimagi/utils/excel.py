import csv

# a *DictReader responsds to __init__(self, file), __iter__, and fieldnames
import os
from tempfile import NamedTemporaryFile
import openpyxl

def CsvDictReader(file):
    return csv.DictReader(file)

class Excel2007DictReader(object):
    def __init__(self, f):
        if isinstance(f, basestring):
            filename = f
        elif not isinstance(f, file):
            tmp = NamedTemporaryFile(mode='wb', suffix='xlsx', delete=False)
            filename = tmp.name
            tmp.write(f.read())
            tmp.close()
        else:
            filename = f

        self.wb = openpyxl.reader.excel.load_workbook(filename, use_iterators=True)
        self.worksheet = self.wb.worksheets[0]
        self.fieldnames = []
        self.fieldnames = [cell.internal_value for cell in self.worksheet.iter_rows().next()]
    def __iter__(self):
        rows = self.worksheet.iter_rows()
        rows.next()
        def to_string(thing):
            if isinstance(thing, int):
                return unicode(thing)
            elif isinstance(thing, float):
                return unicode(int(thing))
            return thing
        for row in rows:
            yield dict(zip(self.fieldnames, [to_string(cell.internal_value) for cell in row]))