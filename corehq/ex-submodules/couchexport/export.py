from contextlib import contextmanager
import itertools
from couchexport.exceptions import (
    SchemaMismatchException,
    UnsupportedExportFormat,
)
from django.conf import settings
from couchexport.models import Format
from couchexport import writers


def get_writer(format, use_formatted_cells=False):
    if format == Format.XLS_2007:
        return writers.Excel2007ExportWriter(use_formatted_cells=use_formatted_cells)
    try:
        return {
            Format.CSV: writers.CsvExportWriter,
            Format.HTML: writers.HtmlExportWriter,
            Format.ZIPPED_HTML: writers.ZippedHtmlExportWriter,
            Format.JSON: writers.JsonExportWriter,
            Format.XLS: writers.Excel2003ExportWriter,
            Format.UNZIPPED_CSV: writers.UnzippedCsvExportWriter,
            Format.PYTHON_DICT: writers.PythonDictWriter,
            Format.GEOJSON: writers.GeoJSONWriter,
        }[format]()
    except KeyError:
        raise UnsupportedExportFormat("Unsupported export format: %s!" % format)


def export_from_tables(tables, file, format, max_column_size=2000):
    writer = get_writer(format)
    sheet_headers = []
    rows_by_sheet = []

    for table in tables:
        worksheet_title, rows = FormattedRow.wrap_all_rows([table])[0]
        row_generator = iter(rows)
        # The first row gets added to sheet_headers, the rest gets added to rows_by_sheet
        sheet_headers.append((worksheet_title, [next(row_generator)]))
        rows_by_sheet.append((worksheet_title, row_generator))

    writer.open(sheet_headers, file, max_column_size=max_column_size)
    writer.write(rows_by_sheet)
    writer.close()


def export_raw(headers, data, file, format=Format.XLS_2007,
               max_column_size=2000, separator='|'):
    """
    Do a raw export from an in-memory representation of headers and data.
    Headers should be a list of (tablename, table) tuples with only one
    row (containing the headers) in the table.

    data_table should have the same format but can support multiple rows
    per table if needed.

    Example:

    headers:
     (("employee", ("id", "name", "gender")),
      ("building", ("id", "name", "address")))

    data:
     (("employee", (("1", "cory", "m"),
                    ("2", "christian", "m"),
                    ("3", "amelia", "f"))),
      ("building", (("1", "dimagi", "585 mass ave."),
                    ("2", "old dimagi", "529 main st."))))

    """
    context = export_raw_to_writer(headers=headers, data=data, file=file, format=format,
                                   max_column_size=max_column_size, separator=separator)
    with context:
        pass


@contextmanager
def export_raw_to_writer(headers, data, file, format=Format.XLS_2007,
                         max_column_size=2000, separator='|'):
    """
    exposing export_raw as a context manager gives the caller the opportunity
    to interact with `writer` before it is closed. The caller could, for example,
    add excel styling or excel properties.

    """
    # transform docs onto output and save
    writer = get_writer(format)

    # format the headers the way the export likes them
    headers = FormattedRow.wrap_all_rows(headers)
    writer.open(headers, file, max_column_size=max_column_size)

    # do the same for the data
    data = FormattedRow.wrap_all_rows(data)
    writer.write(data)
    yield writer
    writer.close()


class Constant(object):

    def __init__(self, message):
        self.message = message

    def __str__(self):
        return self.message


SCALAR_NEVER_WAS = (settings.COUCHEXPORT_SCALAR_NEVER_WAS
    if hasattr(settings, "COUCHEXPORT_SCALAR_NEVER_WAS")
    else "---")

LIST_NEVER_WAS = (settings.COUCHEXPORT_LIST_NEVER_WAS
    if hasattr(settings, "COUCHEXPORT_LIST_NEVER_WAS")
    else "this list never existed")

scalar_never_was = Constant(SCALAR_NEVER_WAS)
list_never_was = Constant(LIST_NEVER_WAS)
transform_error_constant = Constant("---ERR---")


def render_never_was(schema):
    if isinstance(schema, dict):
        answ = {}
        for key in schema:
            answ[key] = render_never_was(schema[key])
        return answ

    elif isinstance(schema, list):
        return list_never_was
    else:
        return scalar_never_was


unknown_type = None


def fit_to_schema(doc, schema):

    def log(msg):
        raise SchemaMismatchException("doc-schema mismatch: %s (%s)" % (msg, doc))

    if schema is None:
        if doc:
            log("%s is not null" % doc)
        return None
    if isinstance(schema, list):
        if not doc:
            doc = []
        if not isinstance(doc, list):
            doc = [doc]
        answ = []
        schema_, = schema
        for doc_ in doc:
            answ.append(fit_to_schema(doc_, schema_))
        return answ
    if isinstance(schema, dict):
        if not doc:
            doc = {}
        if not isinstance(doc, dict):
            doc = {'': doc}
        doc_keys = set(doc.keys())
        schema_keys = set(schema.keys())
        if doc_keys - schema_keys:
            log("doc has keys not in schema: '%s'" % ("', '".join(doc_keys - schema_keys)))
        answ = {}
        for key in schema:
            #if schema[key] == unknown_type: continue
            if key in doc:
                answ[key] = fit_to_schema(doc.get(key), schema[key])
            else:
                answ[key] = render_never_was(schema[key])
        return answ
    if schema == "string":
        if not doc:
            doc = ""
        if not isinstance(doc, str):
            doc = str(doc)
        return doc


def get_headers(schema, separator="|"):
    return _format_tables(
        _create_intermediate_tables(schema, schema),
        include_data=False,
        separator=separator,
    )


def get_formatted_rows(docs, schema, separator, include_headers=True):
    return _format_tables(_create_intermediate_tables(docs, schema),
                          separator=separator, include_headers=include_headers)


def _create_intermediate_tables(docs, schema):
    """
    return {
        table_name: {
            row_id_number: {
                column_name: cell_data,
                ...
            },
            ...
        },
        ...
    }

    """

    INT = '#'

    def lookup(doc, keys):
        for key in keys:
            doc = doc[key]
        return doc

    def split_path(path):
        table = []
        column = []
        id = []
        for k in path:
            if isinstance(k, str):
                if k:
                    column.append(k)
            else:
                table.extend(column)
                table.append(INT)
                column = []
                id.append(k)
        return (tuple(table), tuple(column), tuple(id))

    schema = [schema]
    docs = fit_to_schema(docs, schema)
    # first, flatten documents
    queue = [()]
    leaves = []
    while queue:
        path = queue.pop()
        d = lookup(docs, path)
        if isinstance(d, dict):
            for key in d:
                queue.append(path + (key,))
        elif isinstance(d, list):
            for i, _ in enumerate(d):
                queue.append(path + (i,))
        elif d != list_never_was:
            leaves.append((split_path(path), d))
    leaves.sort()
    tables = {}
    for (table_name, column_name, id), val in leaves:
        table = tables.setdefault(table_name, {})
        row = table.setdefault(id, {})
        row[column_name] = val

    return tables


class FormattedRow(object):
    """
    Simple data structure to represent a row of an export. Just
    a pairing of an id and the data.

    The id should be an iterable (compound ids are supported).
    """

    def __init__(self, data, id=None, separator=".", id_index=0,
                 is_header_row=False, hyperlink_column_indices=(),
                 skip_excel_formatting=()):
        self.data = data
        self.id = id
        self.separator = separator
        self.id_index = id_index
        self.is_header_row = is_header_row
        self.hyperlink_column_indices = hyperlink_column_indices
        self.skip_excel_formatting = skip_excel_formatting

    def __iter__(self):
        for i in self.get_data():
            yield i

    def has_id(self):
        return self.id is not None

    @property
    def formatted_id(self):
        if isinstance(self.id, str):
            return self.id
        return self.separator.join(map(str, self.id))

    def include_compound_id(self):
        return len(self.compound_id) > 1

    @property
    def compound_id(self):
        if isinstance(self.id, str):
            return [self.id]
        return self.id

    def get_data(self):
        if self.has_id():
            # tl;dr:
            # return self.data[:self.id_index] + [self.formatted_id] + data[self.id_index:]
            if self.is_header_row:
                id_block = self.compound_id
            elif self.include_compound_id():
                id_block = [self.formatted_id] + list(self.compound_id)
            else:
                id_block = [self.formatted_id]

            return itertools.chain(
                itertools.islice(self.data, None, self.id_index),
                id_block,
                itertools.islice(self.data, self.id_index, None)
            )
        else:
            return iter(self.data)

    @classmethod
    def wrap_all_rows(cls, tables):
        """
        Take a list of tuples (name, SINGLE_ROW) or (name, (ROW, ROW, ...)). The rows can be generators.
        """

        def coerce_to_list_of_rows(rows):
            rows = iter(rows)
            # peek at the first element, then add it back
            try:
                first_entry = next(rows)
            except StopIteration:
                return rows
            rows = itertools.chain([first_entry], rows)
            if first_entry and (not hasattr(first_entry, '__iter__') or isinstance(first_entry, str)):
                # `rows` is actually just a single row, so wrap it
                return [rows]
            return rows

        return [
            (name, (cls(row) for row in coerce_to_list_of_rows(rows)))
            for name, rows in tables
        ]


def _format_tables(tables, id_label='id', separator='.', include_headers=True,
                   include_data=True):
    """
    tables nested dict structure from _create_intermediate_tables
    return [
        (table_name, [
            (FormattedRow(headers, [id_label], separator) if include_headers),
            FormattedRow(values, id, separator),
            FormattedRow(values, id, separator),
            ...
        ])
    ]

    """
    answ = []
    assert include_data or include_headers, "This method is pretty useless if you don't include anything!"

    for table_name, table in sorted(tables.items()):
        new_table = []
        keys = sorted(list(table.items())[0][1])  # the keys for every row are the same

        if include_headers:
            id_key = [id_label]
            id_len = len(list(table)[0])  # this is a proxy for the complexity of the ID
            if id_len > 1:
                id_key += ["{id}__{count}".format(id=id_label, count=i) for i in range(id_len)]
            header_vals = [separator.join(key) for key in keys]
            new_table.append(FormattedRow(header_vals, id_key, separator,
                                          is_header_row=True))

        if include_data:
            for id, row in sorted(table.items()):
                values = [row[key] for key in keys]
                new_table.append(FormattedRow(values, id, separator))

        answ.append((separator.join(table_name), new_table))
    return answ
