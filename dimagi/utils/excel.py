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
        self.headers = []
        self.worksheet = worksheet
        for cell in self.worksheet.iter_rows().next():
            if cell.internal_value is None:
                break
            else:
                self.headers.append(cell.internal_value)
        self.fieldnames = self.get_fieldnames()

    def get_fieldnames(self):
        obj = {}
        for field, value in zip(self.headers, [''] * len(self.headers)):
            self.set_field_value(obj, field, value)
        return obj.keys()

    @classmethod
    def set_field_value(cls, obj, field, value):
        if isinstance(value, basestring):
            value = value.strip()
        # try dict
        try:
            field, subfield = field.split(':')
        except Exception:
            pass
        else:
            field = field.strip()

            if not obj.has_key(field):
                obj[field] = {}

            cls.set_field_value(obj[field], subfield, value)
            return

        # try list
        try:
            field, _ = field.split()
        except Exception:
            pass
        else:
            dud = {}
            cls.set_field_value(dud, field, value)
            (field, value), = dud.items()

            if not obj.has_key(field):
                obj[field] = []
            if value is not None:
                obj[field].append(value)
            return

        # else flat

        # try boolean
        try:
            field, nothing = field.split('?')
            assert(nothing.strip() == '')
        except Exception:
            pass
        else:
            try:
                value = {
                    'yes': True,
                    'true': True,
                    'no': False,
                    'false': False,
                    '': False,
                    None: False,
                    }[value]
            except AttributeError:
                raise Exception('Values for %s must be: "yes" or "no" (or empty = "no")')

        # set for any flat type
        field = field.strip()
        if obj.has_key(field):
            raise Exception('You have a repeat field: %s' % field)

        obj[field] = value

    def row_to_json(self, row):
        obj = {}

        for cell, header in zip(row, self.headers):
            cell_value = cell.internal_value
            self.set_field_value(obj, header, cell_value)
        return obj

    def __iter__(self):
        rows = self.worksheet.iter_rows()
        # skip header row
        rows.next()
        for row in rows:
            if not filter(lambda cell: cell.internal_value, row):
                break
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
        self.worksheets_by_title = {}
        self.worksheets = []
        for worksheet in self.wb.worksheets:
            ws = WorksheetJSONReader(worksheet)
            self.worksheets_by_title[worksheet.title] = ws
            self.worksheets.append(ws)

    def get_worksheet(self, title=None, index=None):
        if title is not None and index is not None:
            raise TypeError("Can only get worksheet by title *or* index")
        if title:
            return self.worksheets_by_title[title]
        elif index:
            return self.worksheets[index]
        else:
            return self.worksheets[0]
