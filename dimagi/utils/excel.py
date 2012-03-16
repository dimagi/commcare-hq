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

class WorksheetJSONReader(object):
    def __init__(self, worksheet):
        self.fieldnames = []
        self.worksheet = worksheet
        self.fieldnames = [cell.internal_value for cell in self.worksheet.iter_rows().next()]

    def row_to_json(self, row):
        obj = {}
        for cell, fieldname in zip(row, self.fieldnames):
            data = cell.internal_value
            # try dict
            try:
                field, subfield = fieldname.split(':')
            except Exception:
                pass
            else:
                field = field.strip()
                subfield = subfield.strip()
                if not obj.has_key(field):
                    obj[field] = {}
                if obj[field].has_key(subfield):
                    raise Exception('You have a repeat field: %s' % fieldname)
                obj[field][subfield] = data
                continue

            # try list
            try:
                field, _ = fieldname.split()
            except Exception:
                pass
            else:
                field = field.strip()
                if not obj.has_key(field):
                    obj[field] = []
                if data is not None:
                    obj[field].append(data)
                continue

            # else flat
            if obj.has_key(fieldname):
                raise Exception('You have a repeat field: %s' % fieldname)
            field = fieldname.strip()
            obj[field] = data
        return obj

    def __iter__(self):
        rows = self.worksheet.iter_rows()
        # skip header row
        rows.next()
        for row in rows:
            yield self.row_to_json(row)

class WorkbookJSONReader(object):
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
        self.worksheets = {}
        for worksheet in self.wb.worksheets:
            self.worksheets[worksheet.title] = WorksheetJSONReader(worksheet)