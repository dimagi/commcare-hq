from __future__ import absolute_import
from __future__ import unicode_literals
from collections import namedtuple
from datetime import datetime
import hashlib
from itertools import islice
import os
import tempfile
from six.moves.urllib.error import URLError
from dimagi.ext.couchdbkit import Document, DictProperty,\
    DocumentSchema, StringProperty, SchemaListProperty, ListProperty,\
    StringListProperty, DateTimeProperty, SchemaProperty, BooleanProperty, IntegerProperty
import json
import couchexport
from corehq.blobs.mixin import BlobMixin
from couchexport.exceptions import CustomExportValidationError
from couchexport.files import ExportFiles
from couchexport.transforms import identity
from couchexport.util import SerializableFunctionProperty,\
    get_schema_index_view_keys, force_tag_to_list
from memoized import memoized
from dimagi.utils.mixins import UnicodeMixIn
from dimagi.utils.couch.database import get_db, iter_docs
from soil import DownloadBase
from couchdbkit.exceptions import ResourceNotFound
from couchexport.properties import TimeStampProperty, JsonProperty
from dimagi.utils.logging import notify_exception
import six
from six.moves import zip
from six.moves import range


ColumnType = namedtuple('ColumnType', 'cls label')
column_types = {}
display_column_types = {}


class register_column_type(object):

    def __init__(self, label=None):
        self.label = label

    def __call__(self, cls):
        column_types[cls.__name__] = cls
        if self.label:
            display_column_types[cls.__name__] = ColumnType(
                cls=cls,
                label=self.label
            )
        return cls


class Format(object):
    """
    Supported formats go here.
    """
    CSV = "csv"
    ZIP = "zip"
    XLS = "xls"
    XLS_2007 = "xlsx"
    HTML = "html"
    ZIPPED_HTML = "zipped-html"
    JSON = "json"
    PYTHON_DICT = "dict"
    UNZIPPED_CSV = 'unzipped-csv'
    CDISC_ODM = 'cdisc-odm'

    FORMAT_DICT = {CSV: {"mimetype": "application/zip",
                         "extension": "zip",
                         "download": True},
                   ZIP: {"mimetype": "application/zip",
                         "extension": "zip",
                         "download": True},
                   XLS: {"mimetype": "application/vnd.ms-excel",
                         "extension": "xls",
                         "download": True},
                   XLS_2007: {"mimetype": "application/vnd.ms-excel",
                              "extension": "xlsx",
                              "download": True},
                   HTML: {"mimetype": "text/html; charset=utf-8",
                          "extension": "html",
                          "download": False},
                   ZIPPED_HTML: {"mimetype": "application/zip",
                                 "extension": "zip",
                                 "download": True},
                   JSON: {"mimetype": "application/json",
                          "extension": "json",
                          "download": False},
                   PYTHON_DICT: {"mimetype": None,
                          "extension": None,
                          "download": False},
                   UNZIPPED_CSV: {"mimetype": "text/csv",
                                  "extension": "csv",
                                  "download": True},
                   CDISC_ODM: {'mimetype': 'application/cdisc-odm+xml',
                               'extension': 'xml',
                               'download': True},

    }

    VALID_FORMATS = list(FORMAT_DICT)

    def __init__(self, slug, mimetype, extension, download):
        self.slug = slug
        self.mimetype = mimetype
        self.extension = extension
        self.download = download

    @classmethod
    def from_format(cls, format):
        format = format.lower()
        if format not in cls.VALID_FORMATS:
            raise URLError("Unsupported export format: %s!" % format)
        return cls(format, **cls.FORMAT_DICT[format])


class ExportSchema(Document, UnicodeMixIn):
    """
    An export schema that can store intermittent contents of the export so
    that the entire doc list doesn't have to be used to generate the export
    """
    index = JsonProperty()
    schema = DictProperty()
    timestamp = TimeStampProperty()

    def __unicode__(self):
        return "%s: %s" % (json.dumps(self.index), self.timestamp)

    @classmethod
    def wrap(cls, data):
        if data.get('timestamp', '').startswith('1-01-01'):
            data['timestamp'] = '1970-01-01T00:00:00Z'

        return super(ExportSchema, cls).wrap(data)

    @classmethod
    def last(cls, index):
        return cls.view("couchexport/schema_checkpoints",
            startkey=[json.dumps(index), {}],
            endkey=[json.dumps(index)],
            descending=True,
            limit=1,
            include_docs=True,
            reduce=False,
        ).one()

    @classmethod
    def get_all_checkpoints(cls, index):
        doc_ids = [result["id"] for result in cls.get_db().view(
            "couchexport/schema_checkpoints",
            startkey=[json.dumps(index)],
            endkey=[json.dumps(index), {}],
            reduce=False,
        )]
        for doc in iter_docs(cls.get_db(), doc_ids):
            yield cls.wrap(doc)

    _tables = None

    @property
    def tables(self):
        if self._tables is None:
            from couchexport.export import get_headers
            headers = get_headers(self.schema, separator=".")
            self._tables = [(index, row[0]) for index, row in headers]
        return self._tables

    @property
    def table_dict(self):
        return dict(self.tables)

    def get_columns(self, index):
        return ['id'] + self.table_dict[index].data

    def get_all_ids(self, database=None):
        database = database or self.get_db()
        return set(
            [result['id'] for result in database.view(
                        "couchexport/schema_index",
                        reduce=False,
                        **get_schema_index_view_keys(self.index)).all()])

    def get_new_ids(self, database=None):
        database = database or self.get_db()
        assert self.timestamp, 'exports without timestamps are no longer supported.'
        tag_as_list = force_tag_to_list(self.index)
        startkey = tag_as_list + [self.timestamp.isoformat()]
        endkey = tag_as_list + [{}]
        return set(
            [result['id'] for result in database.view(
                        "couchexport/schema_index",
                        reduce=False,
                        startkey=startkey,
                        endkey=endkey)])

    def get_new_docs(self, database=None):
        return iter_docs(self.get_new_ids(database))


@register_column_type('plain')
class ExportColumn(DocumentSchema):
    """
    A column configuration, for export
    """
    index = StringProperty()
    display = StringProperty()
    # signature: transform(val, doc) -> val
    transform = SerializableFunctionProperty(default=None)
    tag = StringProperty()
    is_sensitive = BooleanProperty(default=False)
    show = BooleanProperty(default=False)

    @classmethod
    def wrap(self, data):
        if 'is_sensitive' not in data and data.get('transform', None):
            data['is_sensitive'] = True

        if 'doc_type' in data and \
           self.__name__ == ExportColumn.__name__ and \
           self.__name__ != data['doc_type']:
            if data['doc_type'] in column_types:
                return column_types[data['doc_type']].wrap(data)
            else:
                raise ResourceNotFound('Unknown column type: %s', data)
        else:
            return super(ExportColumn, self).wrap(data)

    def get_display(self):
        return '{primary}{extra}'.format(
            primary=self.display,
            extra=" [sensitive]" if self.is_sensitive else ''
        )

    def to_config_format(self, selected=True):
        return {
            "index": self.index,
            "display": self.display,
            "transform": self.transform.dumps() if self.transform else None,
            "is_sensitive": self.is_sensitive,
            "selected": selected,
            "tag": self.tag,
            "show": self.show,
            "doc_type": self.doc_type,
            "options": [],
            "allOptions": None,
        }


class ComplexExportColumn(ExportColumn):
    """
    A single column config that can represent multiple actual columns
    in the excel sheet.
    """

    def get_headers(self):
        """
        Return a list of headers that this column contributes to
        """
        raise NotImplementedError()

    def get_data(self, value):
        """
        Return a list of data values that correspond to the headers
        """
        raise NotImplementedError()


@register_column_type('multi-select')
class SplitColumn(ComplexExportColumn):
    """
    This class is used to split a value into multiple columns based
    on a set of pre-defined options. It splits the data value assuming it
    is space separated.

    The outputs will have one column for each 'option' and one additional
    column for any values from the data don't appear in the options.

    Each column will have a value of 1 if the data value contains the
    option for that column otherwise the column will be blank.

    e.g.
    options = ['a', 'b']
    column_headers = ['col a', 'col b', 'col extra']

    data_val = 'a c d'
    output = [1, '', 'c d']
    """
    options = StringListProperty()
    ignore_extras = False

    def get_headers(self):
        header = self.display if '{option}' in self.display else "{name} | {option}"
        for option in self.options:
            yield header.format(
                name=self.display,
                option=option
            )
        if not self.ignore_extras:
            yield header.format(
                name=self.display,
                option='extra'
            )

    def get_data(self, value):
        from couchexport.export import Constant

        opts_len = len(self.options)
        if isinstance(value, Constant):
            row = [value] * opts_len
        else:
            row = [None] * opts_len

        if not isinstance(value, six.string_types):
            return row if self.ignore_extras else row + [value]

        values = value.split(' ') if value else []
        for index, option in enumerate(self.options):
            if option in values:
                row[index] = 1
                values.remove(option)

        if self.ignore_extras:
            return row
        else:
            remainder = ' '.join(values) if values else None
            return row + [remainder]

    def to_config_format(self, selected=True):
        config = super(SplitColumn, self).to_config_format(selected)
        config['options'] = self.options
        return config


class ExportTable(DocumentSchema):
    """
    A table configuration, for export
    """
    index = StringProperty()
    display = StringProperty()
    columns = SchemaListProperty(ExportColumn)

    @classmethod
    def wrap(cls, data):
        # hack: manually remove any references to _attachments at runtime
        data['columns'] = [c for c in data['columns'] if not c['index'].startswith("_attachments.")]
        return super(ExportTable, cls).wrap(data)

    @classmethod
    def default(cls, index):
        return cls(index=index, display="", columns=[])

    @property
    @memoized
    def displays_by_index(self):
        return dict((c.index, c.get_display()) for c in self.columns)

    def get_column_configuration(self, all_cols):
        selected_cols = set()
        for c in self.columns:
            if c.doc_type in display_column_types:
                selected_cols.add(c.index)
                yield c.to_config_format()

        for c in all_cols:
            if c not in selected_cols:
                column = ExportColumn(index=c)
                column.display = self.displays_by_index[c] if c in self.displays_by_index else ''
                yield column.to_config_format(selected=False)

    def get_headers_row(self):
        from couchexport.export import FormattedRow
        headers = []
        for col in self.columns:
            if issubclass(type(col), ComplexExportColumn):
                for header in col.get_headers():
                    headers.append(header)
            else:
                display = col.get_display()
                if col.index == 'id':
                    id_len = len(
                        [part for part in self.index.split('.') if part == '#']
                    )
                    headers.append(display)
                    if id_len > 1:
                        for i in range(id_len):
                            headers.append('{id}__{i}'.format(id=display, i=i))
                else:
                    headers.append(display)
        return FormattedRow(headers)

    @property
    @memoized
    def row_positions_by_index(self):
        return dict((h, i) for i, h in enumerate(self._headers) if h in self.displays_by_index)

    @property
    @memoized
    def id_index(self):
        for i, column in enumerate(self.columns):
            if column.index == 'id':
                return i

    def get_items_in_order(self, row):
        from couchexport.export import scalar_never_was
        row_data = list(row.get_data())
        for column in self.columns:
            # If, for example, column.index references a question in a form
            # export and there are no forms that have a value for that question,
            # then that question does not show up in the schema for the export
            # and so column.index won't be found in self.row_positions_by_index.
            # In those cases we want to give a value of '---' to be consistent
            # with other "not applicable" export values.
            try:
                i = self.row_positions_by_index[column.index]
                val = row_data[i]
            except KeyError:
                val = scalar_never_was

            if issubclass(type(column), ComplexExportColumn):
                for value in column.get_data(val):
                    yield column, value
            else:
                yield column, val

    def trim(self, data, doc, apply_transforms, global_transform):
        from couchexport.export import FormattedRow, Constant, transform_error_constant
        if not hasattr(self, '_headers'):
            self._headers = tuple(data[0].get_data())

        # skip first element without copying
        data = islice(data, 1, None)

        rows = []
        for row in data:
            id = None
            cells = []
            for column, val in self.get_items_in_order(row):
                # TRANSFORM BABY!
                if apply_transforms:
                    if column.transform and not isinstance(val, Constant):
                        try:
                            val = column.transform(val, doc)
                        except Exception:
                            val = transform_error_constant
                    elif global_transform:
                        val = global_transform(val, doc)

                if column.index == 'id':
                    id = val
                else:
                    cells.append(val)
            id_index = self.id_index if id else 0
            row_id = row.id if id else None
            rows.append(FormattedRow(cells, row_id, id_index=id_index))
        return rows


class BaseSavedExportSchema(Document):
    # signature: filter(doc)
    filter_function = SerializableFunctionProperty()

    @property
    def default_format(self):
        return Format.XLS_2007

    def transform(self, doc):
        return doc

    @property
    def filter(self):
        return self.filter_function

    @property
    def is_bulk(self):
        return False

    def get_download_task(self, format=None, **kwargs):
        format = format or self.default_format
        download = DownloadBase()
        download.set_task(couchexport.tasks.export_async.delay(
            self,
            download.download_id,
            format=format,
            **kwargs
        ))
        return download

    def export_data_async(self, format=None, **kwargs):
        download = self.get_download_task(format=format, **kwargs)
        return download.get_start_response()

    @property
    def table_name(self):
        if len(self.index) > 2:
            return self.index[2]
        else:
            return "Form"

    def parse_headers(self, headers):
        return headers

    def parse_tables(self, tables):
        """
        :param tables: [('table_name', [rows...])]
        """
        first_row = tables[0][1]
        return [(self.table_name, first_row)]


class DefaultExportSchema(BaseSavedExportSchema):
    index = JsonProperty()
    type = StringProperty()

    @property
    def name(self):
        return self.index

    @property
    def indices(self):
        return [self.index]

    def parse_headers(self, headers):
        first_header = headers[0][1]
        return [(self.table_name, first_header)]

    def remap_tables(self, tables):
        # can be overridden to rename/remove default stuff from exports
        return tables

    def get_export_components(self, previous_export_id=None, filter=None):
        from couchexport.export import get_export_components
        return get_export_components(self.index, previous_export_id, filter=self.filter & filter)

    def get_export_files(self, format='', previous_export_id=None, filter=None,
                         use_cache=True, max_column_size=2000, separator='|', process=None, **kwargs):
        # the APIs of how these methods are broken down suck, but at least
        # it's DRY
        from couchexport.export import get_writer, get_export_components, get_headers, get_formatted_rows
        from django.core.cache import cache
        import hashlib

        export_tag = self.index

        CACHE_TIME = 1 * 60 * 60 # cache for 1 hour, in seconds

        def _build_cache_key(tag, prev_export_id, format, max_column_size):
            def _human_readable_key(tag, prev_export_id, format, max_column_size):
                return "couchexport_:%s:%s:%s:%s" % (tag, prev_export_id, format, max_column_size)
            return hashlib.md5(_human_readable_key(tag, prev_export_id,
                format, max_column_size)).hexdigest()

        # check cache, only supported for filterless queries, currently
        cache_key = _build_cache_key(export_tag, previous_export_id, format, max_column_size)
        if use_cache and filter is None:
            cached_data = cache.get(cache_key)
            if cached_data:
                (tmp, checkpoint) = cached_data
                return ExportFiles(tmp, checkpoint)

        fd, path = tempfile.mkstemp()
        with os.fdopen(fd, 'wb') as tmp:
            schema_index = export_tag
            config, updated_schema, export_schema_checkpoint = get_export_components(schema_index,
                                                                                     previous_export_id, filter)
            if config:
                writer = get_writer(format)

                # get cleaned up headers
                formatted_headers = self.remap_tables(get_headers(updated_schema, separator=separator))
                writer.open(formatted_headers, tmp, max_column_size=max_column_size)

                total_docs = len(config.potentially_relevant_ids)
                if process:
                    DownloadBase.set_progress(process, 0, total_docs)
                for i, doc in config.enum_docs():
                    if self.transform:
                        doc = self.transform(doc)

                    writer.write(self.remap_tables(get_formatted_rows(
                        doc, updated_schema, include_headers=False,
                        separator=separator)))
                    if process:
                        DownloadBase.set_progress(process, i + 1, total_docs)
                writer.close()

            checkpoint = export_schema_checkpoint

        if checkpoint:
            if use_cache:
                cache.set(cache_key, (path, checkpoint), CACHE_TIME)
            return ExportFiles(path, checkpoint)

        return None


class SavedExportSchema(BaseSavedExportSchema, UnicodeMixIn):
    """
    Lets you save an export format with a schema and list of columns
    and display names.
    """

    name = StringProperty()
    default_format = StringProperty()

    is_safe = BooleanProperty(default=False)  # Is the export de-identified?
    # self.index should always match self.schema.index
    # needs to be here so we can use in couch views
    index = JsonProperty()

    # id of an ExportSchema for checkpointed schemas
    schema_id = StringProperty()

    # user-defined table configuration
    tables = SchemaListProperty(ExportTable)

    # For us right now, 'form' or 'case'
    type = StringProperty()

    # ID of  the new style export that it was converted to
    converted_saved_export_id = StringProperty()

    def __unicode__(self):
        return "%s (%s)" % (self.name, self.index)

    def transform(self, doc):
        return doc

    @property
    def global_transform_function(self):
        # will be called on every value in the doc during export
        return identity

    @property
    @memoized
    def schema(self):
        return ExportSchema.get(self.schema_id)

    @property
    def table_name(self):
        return self.sheet_name if self.sheet_name else "%s" % self._id

    @classmethod
    def default(cls, schema, name="", type='form'):
        return cls(name=name, index=schema.index, schema_id=schema.get_id,
                   tables=[ExportTable.default(schema.tables[0][0])], type=type)

    @property
    @memoized
    def tables_by_index(self):
        return dict([t.index, t] for t in self.tables)

    def get_table_configuration(self, index):
        def column_configuration():
            columns = self.schema.get_columns(index)
            if index in self.tables_by_index:
                return list(self.tables_by_index[index].get_column_configuration(columns))
            else:
                return [
                    ExportColumn(
                        index=c,
                        display=''
                    ).to_config_format(selected=False)
                    for c in columns
                ]

        def display():
            if index in self.tables_by_index:
                return self.tables_by_index[index].display
            else:
                return ''

        return {
            "index": index,
            "display": display(),
            "column_configuration": column_configuration(),
            "selected": index in self.tables_by_index
        }

    def get_table_headers(self, override_name=False):
        return ((self.table_name if override_name and i == 0 else t.index, [t.get_headers_row()]) for i, t in enumerate(self.tables))

    @property
    def table_configuration(self):
        return [self.get_table_configuration(index) for index, cols in self.schema.tables]

    def update_schema(self):
        """
        Update the schema for this object to include the latest columns from
        any relevant docs.

        Does NOT save the doc, just updates the in-memory object.
        """
        from couchexport.schema import build_latest_schema
        schema = build_latest_schema(self.index)
        if schema:
            self.set_schema(schema)

    def set_schema(self, schema):
        """
        Set the schema for this object.

        Does NOT save the doc, just updates the in-memory object.
        """
        self.schema_id = schema.get_id

    def trim(self, document_table, doc, apply_transforms=True):
        tables = []
        for table_index, data in document_table:
            if table_index in self.tables_by_index:
                # todo: currently (index, rows) instead of (display, rows); where best to convert to display?
                tables.append((table_index, self.tables_by_index[table_index].trim(
                    data, doc, apply_transforms, self.global_transform_function
                )))
        return tables

    def get_export_components(self, previous_export_id=None, filter=None):
        from couchexport.export import ExportConfiguration

        database = get_db()

        config = ExportConfiguration(database, self.index,
            previous_export_id,
            self.filter & filter)

        # get and checkpoint the latest schema
        updated_schema = config.get_latest_schema()
        export_schema_checkpoint = config.create_new_checkpoint()
        return config, updated_schema, export_schema_checkpoint

    def get_export_files(self, format=None, previous_export=None, filter=None, process=None, max_column_size=None,
                         apply_transforms=True, limit=0, **kwargs):
        from couchexport.export import get_writer, get_formatted_rows
        if not format:
            format = self.default_format or Format.XLS_2007

        config, updated_schema, export_schema_checkpoint = self.get_export_components(previous_export, filter)

        # transform docs onto output and save
        writer = get_writer(format)

        # open the doc and the headers
        formatted_headers = list(self.get_table_headers())
        fd, path = tempfile.mkstemp()
        with os.fdopen(fd, 'wb') as tmp:
            writer.open(
                formatted_headers,
                tmp,
                max_column_size=max_column_size,
                table_titles=dict([
                    (table.index, table.display)
                    for table in self.tables if table.display
                ])
            )

            total_docs = len(config.potentially_relevant_ids)
            if process:
                DownloadBase.set_progress(process, 0, total_docs)
            for i, doc in config.enum_docs():
                if limit and i > limit:
                    break
                if self.transform and apply_transforms:
                    doc = self.transform(doc)
                formatted_tables = self.trim(
                    get_formatted_rows(doc, updated_schema, separator="."),
                    doc,
                    apply_transforms=apply_transforms
                )
                writer.write(formatted_tables)
                if process:
                    DownloadBase.set_progress(process, i + 1, total_docs)

            writer.close()

        if format == Format.PYTHON_DICT:
            return writer.get_preview()

        return ExportFiles(path, export_schema_checkpoint, format)

    def get_preview_data(self, export_filter, limit=50):
        return self.get_export_files(Format.PYTHON_DICT, None, export_filter,
                                     limit=limit)

    def download_data(self, format="", previous_export=None, filter=None, limit=0):
        """
        If there is data, return an HTTPResponse with the appropriate data.
        If there is not data returns None.
        """
        from couchexport.shortcuts import export_response
        files = self.get_export_files(format, previous_export, filter, limit=limit)
        return export_response(files.file, files.format, self.name)

    def to_export_config(self):
        """
        Return an ExportConfiguration object that represents this.
        """
        # confusingly, the index isn't the actual index property,
        # but is the index appended with the id to this document.
        # this is to avoid conflicts among multiple exports
        index = "%s-%s" % (self.index, self._id) if isinstance(self.index, six.string_types) else \
            self.index + [self._id] # self.index required to be a string or list
        return ExportConfiguration(index=index, name=self.name,
                                   format=self.default_format)

    def custom_validate(self):
        if self.default_format == Format.XLS:
            for table in self.tables:
                if len(table.columns) > 255:
                    raise CustomExportValidationError("XLS files can only have 255 columns")

    # replaces `sheet_name = StringProperty()`
    def __get_sheet_name(self):
        return self.tables[0].display

    def __set_sheet_name(self, value):
        self.tables[0].display = value

    sheet_name = property(__get_sheet_name, __set_sheet_name)

    @classmethod
    def wrap(cls, data):
        # since this is a property now, trying to wrap it will fail hard
        if 'sheet_name' in data:
            del data['sheet_name']
        return super(SavedExportSchema, cls).wrap(data)


class ExportConfiguration(DocumentSchema):
    """
    Just a way to configure a single export. Used in the group export config.
    """
    index = JsonProperty()
    name = StringProperty()
    format = StringProperty()

    @property
    def filename(self):
        return "%s.%s" % (self.name, Format.from_format(self.format).extension)

    @property
    def type(self):
        # hack - make this backwards compatible with form/case categorization
        # these might only exist in the care-bihar domain or wherever else
        # they've been manually created in the DB.
        try:
            return 'form' if 'http:' in self.index[1] else 'case'
        except IndexError:
            # arbitrarily choose default so it doesn't stay hidden from the UI forever.
            return 'form'

    def __repr__(self):
        return ('%s (%s)' % (self.name, self.index)).encode('utf-8')


class GroupExportComponent(object):
    """
    Helper wrapper class for components of a GroupExportConfiguration
    """

    def __init__(self, config, saved_version, group_id, index):
        self.config = config
        self.saved_version = saved_version
        self.group_id = group_id
        self.index = index


class GroupExportConfiguration(Document):
    """
    An export configuration allows you to setup a collection of exports
    that all run together. Used by the management command or a scheduled
    job to run a bunch of exports on a schedule.
    """
    full_exports = SchemaListProperty(ExportConfiguration)
    custom_export_ids = StringListProperty()

    def get_custom_exports(self):
        for custom in list(self.custom_export_ids):
            custom_export = self._get_custom(custom)
            if custom_export:
                yield custom_export

    def _get_custom(self, custom_id):
        """
        Get a custom export, or delete it's reference if not found
        """
        try:
            return SavedExportSchema.get(custom_id)
        except ResourceNotFound:
            try:
                self.custom_export_ids.remove(custom_id)
                self.save()
            except ValueError:
                pass

    @property
    @memoized
    def saved_exports(self):
        return self._saved_exports_from_configs(self.all_configs)

    def _saved_exports_from_configs(self, configs):
        exports = SavedBasicExport.view(
            "couchexport/saved_exports",
            keys=[json.dumps(config.index) for config in configs],
            include_docs=True,
            reduce=False,
        ).all()
        export_map = dict((json.dumps(export.configuration.index), export) for export in exports)
        return [
            GroupExportComponent(
                config, export_map.get(json.dumps(config.index), None),
                self._id, list(self.all_configs).index(config)
            )
            for config in configs
        ]

    @property
    @memoized
    def all_configs(self):
        """
        Return an iterator of config-like objects that include the
        main configs + the custom export configs.
        """
        return [full for full in self.full_exports] + \
               [custom.to_export_config() for custom in self.get_custom_exports()]

    @property
    def all_export_schemas(self):
        """
        Return an iterator of ExportSchema-like objects that include the
        main configs + the custom export configs.
        """
        for full in self.full_exports:
            yield DefaultExportSchema(index=full.index, type=full.type)
        for custom in self.get_custom_exports():
            yield custom

    @property
    @memoized
    def all_exports(self):
        """
        Returns an iterator of tuples consisting of the export config
        and an ExportSchema-like document that can be used to get at
        the data.
        """
        return list(zip(self.all_configs, self.all_export_schemas))


class SavedBasicExport(BlobMixin, Document):
    """
    A cache of an export that lives in couch.
    Doesn't do anything smart, just works off an index
    """
    configuration = SchemaProperty(ExportConfiguration)
    last_updated = DateTimeProperty()
    last_accessed = DateTimeProperty()
    is_safe = BooleanProperty(default=False)

    @property
    def size(self):
        try:
            return self.blobs[self.get_attachment_name()].content_length
        except KeyError:
            return 0

    def has_file(self):
        return self.get_attachment_name() in self.blobs

    def get_attachment_name(self):
        # obfuscate this because couch doesn't like attachments that start with underscores
        return hashlib.md5(six.text_type(self.configuration.filename).encode('utf-8')).hexdigest()

    def set_payload(self, payload):
        self.put_attachment(payload, self.get_attachment_name())

    def get_payload(self, stream=False):
        return self.fetch_attachment(self.get_attachment_name(), stream=stream)

    @classmethod
    def by_index(cls, index):
        return SavedBasicExport.view(
            "couchexport/saved_exports",
            key=json.dumps(index),
            include_docs=True,
            reduce=False,
        ).all()
