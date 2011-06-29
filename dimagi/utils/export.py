import csv
from StringIO import StringIO
import zipfile

class WorkBook(object):
    _undefined = None
    @property
    def undefined(self):
        return self._undefined

    def open(self, table, headers):
        pass

    def write_row(self, table, row):
        pass

class CsvWorkBook(WorkBook):
    def __init__(self):
        self._writers = {}

    def open(self, table, headers):
        f = StringIO()
        writer = csv.DictWriter(f, headers)
        try:
            writer.writeheader()
        except AttributeError:
            f.write(",".join(headers))
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
    