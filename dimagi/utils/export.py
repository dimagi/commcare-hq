from StringIO import StringIO
from couchexport.export import export_from_tables

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
        headers = self._tables[table][0]
        for key in row:
            if key not in headers:
                raise AttributeError()
        self._tables[table].append([
            row.get(h) for h in headers
        ])

    def format(self, format):
        tables = self._tables.items()
        f = StringIO()
        export_from_tables(tables, f, format)
        return f.getvalue()
