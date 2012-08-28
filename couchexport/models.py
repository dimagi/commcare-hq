import uuid
from couchdbkit.ext.django.schema import Document, IntegerProperty, DictProperty,\
    Property, DocumentSchema, StringProperty, SchemaListProperty, ListProperty,\
    StringListProperty, DateTimeProperty, SchemaProperty
import json
from StringIO import StringIO
import couchexport
from couchexport.util import SerializableFunctionProperty
from dimagi.utils.decorators.memoized import memoized
from dimagi.utils.mixins import UnicodeMixIn
from dimagi.utils.couch.database import get_db
from soil import DownloadBase

class Format(object):
    """
    Supported formats go here.
    """
    CSV = "csv"
    XLS = "xls"
    XLS_2007 = "xlsx"
    HTML = "html"
    JSON = "json"
    
    FORMAT_DICT = {CSV: {"mimetype": "application/zip",
                         "extension": "zip",
                         "download": True},
                   XLS: {"mimetype": "application/vnd.ms-excel",
                         "extension": "xls",
                         "download": True},
                   XLS_2007: {"mimetype": "application/vnd.ms-excel",
                              "extension": "xlsx",
                              "download": True},
                   HTML: {"mimetype": "text/html",
                          "extension": "html",
                          "download": False},
                   JSON: {"mimetype": "application/json",
                          "extension": "json",
                          "download": False}}
    
    VALID_FORMATS = FORMAT_DICT.keys()
    
    def __init__(self, slug, mimetype, extension, download):
        self.slug = slug
        self.mimetype = mimetype
        self.extension = extension
        self.download = download
    
    @classmethod
    def from_format(cls, format):
        format = format.lower()
        if format not in cls.VALID_FORMATS:
            raise ValueError("Unsupported export format: %s!" % format)
        return cls(format, **cls.FORMAT_DICT[format])

class JsonProperty(Property):
    """
    A property that stores data in an arbitrary JSON object.
    """
    
    def to_python(self, value):
        return json.loads(value)

    def to_json(self, value):
        return json.dumps(value)

class ExportSchema(Document, UnicodeMixIn):
    """
    An export schema that can store intermittent contents of the export so
    that the entire doc list doesn't have to be used to generate the export
    """
    index = JsonProperty()
    seq = IntegerProperty()
    schema = DictProperty()
    
    def __unicode__(self):
        return "%s: %s" % (json.dumps(self.index), self.seq)
    
    @classmethod
    def last(cls, index):
        return cls.view("couchexport/schema_checkpoints", 
                        startkey=[json.dumps(index), {}],
                        endkey=[json.dumps(index)],
                        descending=True, limit=1,
                        include_docs=True).one()
                                 
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
    
    @property
    def top_level_nodes(self):
        return self.tables[0][1].get_data()
    
    def get_columns(self, index):
        return self.table_dict[index].get_data()

class ExportColumn(DocumentSchema):
    """
    A column configuration, for export
    """
    index = StringProperty()
    display = StringProperty()

class ExportTable(DocumentSchema):
    """
    A table configuration, for export
    """
    index = StringProperty()
    display = StringProperty()
    columns = SchemaListProperty(ExportColumn)
    order = ListProperty()
    
    @classmethod
    def default(cls, index):
        return cls(index=index, display="", columns=[])
        
    @property
    def col_dict(self):
        if not hasattr(self, "_col_dict"):
            self._col_dict = dict([c.index, c.display] for c in self.columns)
        return self._col_dict
    
    def get_column_configuration(self, schema):
        all_cols = schema.top_level_nodes
        cols = []
        for c in self.columns:
            cols.append({"index": c.index, "display": c.display, "selected": True})
            all_cols = filter(lambda x: x != c.index, all_cols) # exclude
        cols.extend([{"index": c,
                 "display": self.col_dict[c] if c in self.col_dict else c,
                 "selected": c in self.col_dict} for c in all_cols])
        #cols.sort(key=lambda x: not x["selected"])
        return cols
    
    def get_headers_row(self):
        from couchexport.export import FormattedRow
        return FormattedRow([self.col_dict[col] for col in map(lambda x: x.index, self.columns)])
    
    def trim(self, data):
        from couchexport.export import FormattedRow

        headers = data[0]
        if not hasattr(self, "header_to_index_map"):
            self._header_to_index_map = dict([(h, i) \
                                    for i, h in enumerate(headers.get_data()) \
                                    if h in self.col_dict])
        if not hasattr(self, "_cols"):
            self._cols = map(lambda x: x.index, self.columns)
        
        data = data[1:]
        ret = []
        for row in data:
            row_data = list(row.get_data())
            id = row_data[self._header_to_index_map["id"]] if "id" in self._cols else None
            ret.append(FormattedRow([row_data[self._header_to_index_map[col]] \
                                              for col in self._cols if col != "id"], 
                                    id, id_index=self._cols.index("id") if id else 0))

        return ret

class BaseSavedExportSchema(Document):
    # signature: filter(doc)
    filter_function = SerializableFunctionProperty()
    # signature: transform(doc)
    transform = SerializableFunctionProperty(default=None)

    @property
    def filter(self):
        return self.filter_function

    @property
    def is_bulk(self):
        return False

    def export_data_async(self, filter, filename, previous_export_id, format, max_column_size=None):
        format = format or Format.XLS_2007
        download = DownloadBase()
        download.set_task(couchexport.tasks.export_async.delay(
            self,
            download.download_id,
            format=format,
            filename=filename,
            previous_export_id=previous_export_id,
            filter=filter,
            max_column_size=max_column_size
        ))
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
        first_row = tables[0][1]
        return [(self.table_name, first_row)]

class FakeSavedExportSchema(BaseSavedExportSchema):
    index = JsonProperty()

    @property
    def name(self):
        return self.index

    @property
    def indices(self):
        return [self.index]

    def parse_headers(self, headers):
        first_header = headers[0][1]
        return [(self.table_name, first_header)]

    def get_export_components(self, previous_export_id=None, filter=None):
        from couchexport.export import get_export_components
        return get_export_components(self.index, previous_export_id, filter)

    def get_export_files(self, format=None, previous_export_id=None, filter=None,
                         use_cache=True, max_column_size=2000, separator='|', process=None):
        # the APIs of how these methods are broken down suck, but at least
        # it's DRY
        from couchexport.export import export
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
        cache_key = _build_cache_key(export_tag, previous_export_id,
            format, max_column_size)
        if use_cache and filter is None:
            cached_data = cache.get(cache_key)
            if cached_data:
                (tmp, checkpoint) = cached_data
                return tmp, checkpoint

        tmp = StringIO()
        checkpoint = export(export_tag, tmp, format=format,
            previous_export_id=previous_export_id,
            filter=filter, max_column_size=max_column_size,
            separator=separator, export_object=self, process=process)

        if checkpoint:
            if use_cache:
                cache.set(cache_key, (tmp, checkpoint), CACHE_TIME)
            return tmp, checkpoint

        return None, None # hacky empty case


class SavedExportSchema(BaseSavedExportSchema, UnicodeMixIn):
    """
    Lets you save an export format with a schema and list of columns
    and display names.
    """

    name = StringProperty()
    default_format = StringProperty()

    # self.index should always match self.schema.index
    # needs to be here so we can use in couch views
    index = JsonProperty()

    # id of an ExportSchema for checkpointed schemas
    schema_id = StringProperty()

    # user-defined table configuration
    tables = SchemaListProperty(ExportTable)

    # For us right now, 'form' or 'case'
    type = StringProperty()

    def __unicode__(self):
        return "%s (%s)" % (self.name, self.index)

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
        
    def get_table_configuration(self, index):
        table_dict = dict([t.index, t] for t in self.tables)
        return {"index": index, 
                "display": table_dict[index].display if index in table_dict else index,
                "column_configuration": table_dict[index].get_column_configuration(self.schema) \
                                            if index in table_dict else \
                                            [{"index": c, "display": c, 
                                              "selected": False} for c in self.schema.get_columns(index)],
                 "selected": index in table_dict} 
    
    def get_table_headers(self, override_name=False):
        return ((self.table_name if override_name and i==0 else t.index, [t.get_headers_row()]) for i, t in enumerate(self.tables))
        
    @property
    def table_configuration(self):
        return [self.get_table_configuration(index) \
                for index, cols in self.schema.tables]

    def trim(self, document_table):
        if not hasattr(self, "_table_dict"):
            self._table_dict = dict([t.index, t] for t in self.tables)
        
        trimmed_tables = []
        for table_index, data in document_table:
            if table_index in self._table_dict:
                trimmed_tables.append((# self._table_dict[table_index].display,
                                       table_index, # TODO: figure out a way to separate index from display 
                                       self._table_dict[table_index].trim(data)))
        return trimmed_tables

    def get_export_components(self, previous_export_id=None, filter=None):
        from couchexport.export import get_schema_new
        from couchexport.export import ExportConfiguration

        database = get_db()

        config = ExportConfiguration(database, self.index,
            previous_export_id,
            self.filter & filter)

        # get and checkpoint the latest schema
        updated_schema = get_schema_new(config)
        export_schema_checkpoint = ExportSchema(seq=config.current_seq,
            schema=updated_schema,
            index=config.schema_index)
        export_schema_checkpoint.save()

        return config, updated_schema, export_schema_checkpoint
    
    def get_export_files(self, format="", previous_export=None, filter=None, process=None, max_column_size=None):
        from couchexport.export import get_writer, format_tables, create_intermediate_tables

        if not format:
            format = self.default_format or Format.XLS_2007

        config, updated_schema, export_schema_checkpoint = self.get_export_components(previous_export, filter)

        # transform docs onto output and save
        writer = get_writer(format)
        
        # open the doc and the headers
        formatted_headers = list(self.get_table_headers())
        tmp = StringIO()
        writer.open(formatted_headers, tmp, max_column_size=max_column_size)

        total_docs = len(config.potentially_relevant_ids)
        if process:
            DownloadBase.set_progress(process, 0, total_docs)
        for i, doc in config.enum_docs():
            if self.transform:
                doc = self.transform(doc)
            formatted_tables = self.trim(
                format_tables(
                    create_intermediate_tables(doc, updated_schema),
                    separator="."
                )
            )
            writer.write(formatted_tables)
            if process:
                DownloadBase.set_progress(process, i + 1, total_docs)

        writer.close()
        # hacky way of passing back the new format
        tmp.format = format
        return tmp, export_schema_checkpoint

    def download_data(self, format="", previous_export=None, filter=None):
        """
        If there is data, return an HTTPResponse with the appropriate data.
        If there is not data returns None.
        """
        from couchexport.shortcuts import export_response
        tmp, _ = self.get_export_files(format, previous_export, filter)
        return export_response(tmp, tmp.format, self.name)

    class sheet_name(object):
        """replaces: `sheet_name = StringProperty()`: store in tables[0].display instead"""

        @classmethod
        def __get__(cls, instance, owner):
            return instance.tables[0].display

        @classmethod
        def __set__(cls, instance, value):
            instance.tables[0].display = value

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
    
class GroupExportConfiguration(Document):
    """
    An export configuration allows you to setup a collection of exports
    that all run together. Used by the management command or a scheduled
    job to run a bunch of exports on a schedule.
    """
    full_exports = SchemaListProperty(ExportConfiguration)
    custom_export_ids = StringListProperty()
    
    @property
    def saved_exports(self):
        if not hasattr(self, "_saved_exports"):
            self._saved_exports = \
                [(export_config, 
                  SavedBasicExport.view("couchexport/saved_exports", 
                                        key=json.dumps(export_config.index),
                                        include_docs=True,
                                        reduce=False).one()) \
                 for export_config in self.full_exports]
        return self._saved_exports
    
class SavedBasicExport(Document):
    """
    A cache of an export that lives in couch.
    Doesn't do anything smart, just works off an index
    """
    configuration = SchemaProperty(ExportConfiguration) 
    last_updated = DateTimeProperty()
    
    @property
    def size(self):
        return self._attachments[self.configuration.filename]["length"]



class FakeCheckpoint(object):
    @property
    def get_id(self):
        return uuid.uuid4().hex