import csv
from StringIO import StringIO
import zipfile
from couchexport.export import export_from_tables

class RowLengthError(Exception):
    pass

class WorkBook(object):
    _undefined = None
    @property
    def undefined(self):
        return self._undefined

    def __init__(self):
        self._tables = {}

    def open(self, table, headers):
        self._tables[table] = [[h for h in headers],]

    def write_row(self, table, row):
        if len(row) != len(self._tables[table][0]):
            raise RowLengthError()
        self._tables[table].append(row)

    def format(self, format):
        tables = self._tables.items()
        f = StringIO()
        export_from_tables(tables, f, format)
        return f

class CsvWorkBook(WorkBook):
    def __init__(self):
        self._writers = {}

    def open(self, table, headers):
        f = StringIO()
        writer = csv.DictWriter(f, headers)
        try:
            writer.writeheader()
        except AttributeError:
            f.write(",".join([h.encode('utf-8') for h in headers]))
            f.write("\n")

        self._writers[table] = (f, writer)

    def write_row(self, table, row):
        _, writer = self._writers[table]
        for key in row:
            if isinstance(row[key], unicode):
                row[key] = row[key].encode('utf-8')
        writer.writerow(row)

    def to_zip(self):
        zip_io = StringIO()
        zip = zipfile.ZipFile(zip_io, 'w')
        for (table, (f, writer)) in self._writers.items():
            zip.writestr('{table}.csv'.format(table=table), f.getvalue())
        zip.close()
        return zip_io.getvalue()
