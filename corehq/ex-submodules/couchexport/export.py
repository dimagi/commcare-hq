from __future__ import absolute_import
from contextlib import contextmanager
import itertools
from couchexport.exceptions import SchemaMismatchException,\
    UnsupportedExportFormat
from couchexport.schema import extend_schema
from django.conf import settings
from couchexport.models import ExportSchema, Format
from dimagi.utils.mixins import UnicodeMixIn
from dimagi.utils.couch.database import get_db, iter_docs
from couchexport import writers
from dimagi.utils.decorators.memoized import memoized
from couchexport.util import get_schema_index_view_keys, default_cleanup
from datetime import datetime


class ExportConfiguration(object):
    """
    A representation of the configuration parameters for an export and
    some functions to actually facilitate the export from this config.
    """

    def __init__(self, database, schema_index, previous_export=None, filter=None,
                 disable_checkpoints=False, cleanup_fn=default_cleanup):
        self.database = database
        if len(schema_index) > 2:
            schema_index = schema_index[0:2]
        self.schema_index = schema_index
        self.previous_export = previous_export
        self.filter = filter
        self.timestamp = datetime.utcnow()
        self.potentially_relevant_ids = self._potentially_relevant_ids()
        self.disable_checkpoints = disable_checkpoints
        self.cleanup_fn = cleanup_fn

    def include(self, document):
        """
        Returns True if the document should be included in the results,
        otherwise false
        """
        return self.filter(document) if self.filter else True

    def cleanup(self, document_or_schema):
        """
        Given a doc or schema, pass it through a cleanup function prior to mapping
        to remove potential unwanted properties. One example of this is to remove
        the overly verbose _attachments fields.
        """
        return self.cleanup_fn(document_or_schema) if self.cleanup_fn else document_or_schema

    @property
    @memoized
    def all_doc_ids(self):
        """
        Gets view results for all documents matching this schema
        """
        return set([result['id'] for result in \
                    self.database.view(
                        "couchexport/schema_index",
                        reduce=False,
                        **get_schema_index_view_keys(self.schema_index)
                    ).all()])

    def _potentially_relevant_ids(self):
        return self.previous_export.get_new_ids() if self.previous_export \
            else self.all_doc_ids

    def get_potentially_relevant_docs(self):
        return iter_docs(self.database, self.potentially_relevant_ids)

    def enum_docs(self):
        """
        yields (index, doc) tuples for docs that pass the filter
        index counts number of docs processed so far
        NOT the number of docs returned so far

        Useful for progress bars which use
        len(self.potentially_relevant_ids) as the total.

        """
        for i, doc in enumerate(self.get_potentially_relevant_docs()):
            if self.include(doc):
                yield i, self.cleanup(doc)

    def get_docs(self):
        for _, doc in self.enum_docs():
            yield doc

    def last_checkpoint(self):
        return None if self.disable_checkpoints else ExportSchema.last(self.schema_index)

    @memoized
    def get_latest_schema(self):
        last_export = self.last_checkpoint()
        schema = self.cleanup(dict(last_export.schema) if last_export and last_export.schema else None)
        doc_ids = last_export.get_new_ids(self.database) if last_export else self.all_doc_ids
        for doc in iter_docs(self.database, doc_ids):
            schema = extend_schema(schema, self.cleanup(doc))
        return schema

    def create_new_checkpoint(self):
        checkpoint = ExportSchema(
            schema=self.get_latest_schema(),
            timestamp=self.timestamp,
            index=self.schema_index,
        )
        checkpoint.save()
        return checkpoint


def get_writer(format):
    try:
        return {
            Format.CSV: writers.CsvExportWriter,
            Format.HTML: writers.HtmlExportWriter,
            Format.ZIPPED_HTML: writers.ZippedHtmlExportWriter,
            Format.JSON: writers.JsonExportWriter,
            Format.XLS: writers.Excel2003ExportWriter,
            Format.XLS_2007: writers.Excel2007ExportWriter,
            Format.UNZIPPED_CSV: writers.UnzippedCsvExportWriter,
            Format.CDISC_ODM: writers.CdiscOdmExportWriter,
            Format.PYTHON_DICT: writers.PythonDictWriter,
        }[format]()
    except KeyError:
        raise UnsupportedExportFormat("Unsupported export format: %s!" % format)


def export_from_tables(tables, file, format, max_column_size=2000):
    tables = FormattedRow.wrap_all_rows(tables)
    writer = get_writer(format)
    writer.open(tables, file, max_column_size=max_column_size)
    writer.write(tables, skip_first=True)
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


def get_export_components(schema_index, previous_export_id=None, filter=None):
    """
    Get all the components needed to build an export file.
    """

    previous_export = ExportSchema.get(previous_export_id)\
        if previous_export_id else None
    database = get_db()
    config = ExportConfiguration(database, schema_index,
        previous_export, filter)

    # handle empty case
    if not config.potentially_relevant_ids:
        return None, None, None

    # get and checkpoint the latest schema
    updated_schema = config.get_latest_schema()
    export_schema_checkpoint = config.create_new_checkpoint()

    return config, updated_schema, export_schema_checkpoint


class Constant(UnicodeMixIn):

    def __init__(self, message):
        self.message = message

    def __unicode__(self):
        return self.message

SCALAR_NEVER_WAS = settings.COUCHEXPORT_SCALAR_NEVER_WAS \
                    if hasattr(settings, "COUCHEXPORT_SCALAR_NEVER_WAS") \
                    else "---"

LIST_NEVER_WAS = settings.COUCHEXPORT_LIST_NEVER_WAS \
                    if hasattr(settings, "COUCHEXPORT_LIST_NEVER_WAS") \
                    else "this list never existed"

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
            if doc.has_key(key):
                answ[key] = fit_to_schema(doc.get(key), schema[key])
            else:
                answ[key] = render_never_was(schema[key])
        return answ
    if schema == "string":
        if not doc:
            doc = ""
        if not isinstance(doc, basestring):
        #log("%s is not a string" % doc)
            doc = unicode(doc)
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
            if isinstance(k, basestring):
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
                 is_header_row=False):
        self.data = data
        self.id = id
        self.separator = separator
        self.id_index = id_index
        self.is_header_row = is_header_row

    def __iter__(self):
        for i in self.get_data():
            yield i

    def has_id(self):
        return self.id is not None

    @property
    def formatted_id(self):
        if isinstance(self.id, basestring):
            return self.id
        return self.separator.join(map(unicode, self.id))

    def include_compound_id(self):
        return len(self.compound_id) > 1

    @property
    def compound_id(self):
        if isinstance(self.id, basestring):
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
        Take a list of tuples (name, SINGLE_ROW) or (name, (ROW, ROW, ...))
        """
        ret = []
        for name, rows in tables:
            rows = list(rows)
            if rows and (not hasattr(rows[0], '__iter__') or isinstance(rows[0], basestring)):
                # `rows` is actually just a single row, so wrap it
                rows = [rows]
            ret.append(
                (name, [cls(row) for row in rows])
            )
        return ret


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
        keys = sorted(table.items()[0][1].keys()) # the keys for every row are the same

        if include_headers:
            id_key = [id_label]
            id_len = len(table.keys()[0]) # this is a proxy for the complexity of the ID
            if id_len > 1:
                id_key += ["{id}__{count}".format(id=id_label, count=i) \
                           for i in range(id_len)]
            header_vals = [separator.join(key) for key in keys]
            new_table.append(FormattedRow(header_vals, id_key, separator,
                                          is_header_row=True))

        if include_data:
            for id, row in sorted(table.items()):
                values = [row[key] for key in keys]
                new_table.append(FormattedRow(values, id, separator))

        answ.append((separator.join(table_name), new_table))
    return answ
