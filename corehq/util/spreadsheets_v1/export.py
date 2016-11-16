from couchexport.export import get_writer


class WorkBook(object):
    _undefined = '---'

    @property
    def undefined(self):
        return self._undefined

    def __init__(self, file, format):
        self._headers = {}
        self.writer = get_writer(format.slug)
        self.file = file
        self.writer.open((), file)

    def open(self, table_name, headers):
        self.writer.add_table(table_name, headers)
        self._headers[table_name] = headers

    def write_row(self, table_name, row):
        headers = self._headers[table_name]
        for key in row:
            if key not in headers:
                raise AttributeError()
        self.writer.write_row(table_name, [row.get(h) for h in headers])

    def close(self):
        self.writer.close()
