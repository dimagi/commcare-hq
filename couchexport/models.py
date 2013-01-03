from itertools import islice
from couchdbkit.ext.django.schema import Document, IntegerProperty, DictProperty,\
    DocumentSchema, StringProperty, SchemaListProperty, ListProperty,\
    StringListProperty, DateTimeProperty, SchemaProperty, BooleanProperty
import json
from StringIO import StringIO
import couchexport
from couchexport.util import SerializableFunctionProperty,\
    get_schema_index_view_keys, force_tag_to_list
from dimagi.utils.decorators.memoized import memoized
from dimagi.utils.mixins import UnicodeMixIn
from dimagi.utils.couch.database import get_db, iter_docs
from soil import DownloadBase
from couchdbkit.exceptions import ResourceNotFound
from couchexport.properties import TimeStampProperty, JsonProperty
from couchdbkit.consumer import Consumer

class Format(object):
    """
    Supported formats go here.
    """
    CSV = "csv"
    ZIP = "zip"
    XLS = "xls"
    XLS_2007 = "xlsx"
    HTML = "html"
    JSON = "json"
    
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

class ExportSchema(Document, UnicodeMixIn):
    """
    An export schema that can store intermittent contents of the export so
    that the entire doc list doesn't have to be used to generate the export
    """
    index = JsonProperty()
    seq = IntegerProperty() # semi-deprecated
    schema = DictProperty()
    timestamp = TimeStampProperty()

    def __unicode__(self):
        return "%s: %s" % (json.dumps(self.index), self.seq)

    @classmethod
    def wrap(cls, data):
        # this isn't the cleanest nor is it perfect but in the event
        # this doc traversed databases somehow and now has a bad seq
        # id, make sure to just reset it to 0.
        # This won't catch if the seq is bad but not greater than the
        # current one).
        ret = super(ExportSchema, cls).wrap(data)
        current_seq = cls.get_db().info()["update_seq"]
        if current_seq < ret.seq:
            ret.seq = 0
            ret.save()
        # TODO: handle seq -> datetime migration
        return ret

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

    def get_all_ids(self, database=None):
        database = database or self.get_db()
        return set(
            [result['id'] for result in database.view(
                        "couchexport/schema_index",
                        reduce=False,
                        **get_schema_index_view_keys(self.index)).all()])

    def get_new_ids(self, database=None):
        # TODO: deprecate/remove old way of doing this
        database = database or self.get_db()
        if self.timestamp:
            return self._ids_by_timestamp(database)
        else:
            return self._ids_by_seq(database)

    def _ids_by_seq(self, database):
        if self.seq == 0:
            return self.get_all_ids()

        consumer = Consumer(database)
        view_results = consumer.fetch(since=self.seq)
        if view_results:
            include_ids = set([res["id"] for res in view_results["results"]])
            return include_ids.intersection(self.get_all_ids())
        else:
            # sometimes this comes back empty. I think it might be a bug
            # in couchdbkit, but it's impossible to consistently reproduce.
            # For now, just assume this is fine.
            return set()

    def _ids_by_timestamp(self, database):
        tag_as_list = force_tag_to_list(self.index)
        startkey = tag_as_list + self.timestamp
        endkey = tag_as_list + {}
        return set(
            [result['id'] for result in database.view(
                        "couchexport/schema_index",
                        reduce=False,
                        startkey=startkey,
                        endkey=endkey)])

    def get_new_docs(self, database=None):
        return iter_docs(self.get_new_ids(database))

class ExportColumn(DocumentSchema):
    """
    A column configuration, for export
    """
    index = StringProperty()
    display = StringProperty()
    # signature: transform(val, doc) -> val
    transform = SerializableFunctionProperty(default=None)

    def to_config_format(self, selected=True):
        return {
            "index": self.index,
            "display": self.display,
            "transform": self.transform.dumps() if self.transform else None,
            "selected": selected,
        }

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
    @memoized
    def displays_by_index(self):
        return dict((c.index, c.display + (" [sensitive]" if c.transform else '')) for c in self.columns)
    
    def get_column_configuration(self, schema):
        all_cols = schema.top_level_nodes
        selected_cols = set()
        for c in self.columns:
            selected_cols.add(c.index)
            yield c.to_config_format()

        for c in all_cols:
            if c not in selected_cols:
                column = ExportColumn(index=c)
                column.display = self.displays_by_index[c] if self.displays_by_index.has_key(c) else c
                yield column.to_config_format(selected=False)

    def get_headers_row(self):
        from couchexport.export import FormattedRow
        return FormattedRow([self.displays_by_index[col.index] for col in self.columns])

    @property
    @memoized
    def row_positions_by_index(self):
        return dict((h, i) for i, h in enumerate(self._headers) if self.displays_by_index.has_key(h))

    @property
    @memoized
    def id_index(self):
        for i, column in enumerate(self.columns):
            if column.index == 'id':
                return i

    def get_items_in_order(self, row):
        row_data = list(row.get_data())
        for column in self.columns:
            i = self.row_positions_by_index[column.index]
            val = row_data[i]
            yield column, val

    def trim(self, data, doc, apply_transforms):
        from couchexport.export import FormattedRow, Constant, transform_error_constant
        if not hasattr(self, '_headers'):
            self._headers = tuple(data[0].get_data())

        # skip first element without copying
        data = islice(data, 1, None)

        for row in data:
            id = None
            cells = []
            for column, val in self.get_items_in_order(row):
                # DEID TRANSFORM BABY!
                if apply_transforms and column.transform and not isinstance(val, Constant):
                    try:
                        val = column.transform(val, doc)
                    except Exception:
                        val = transform_error_constant
                if column.index == 'id':
                    id = val
                else:
                    cells.append(val)
            id_index = self.id_index if id else 0
            row_id = row.id if id else None
            yield FormattedRow(cells, row_id, id_index=id_index)

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

    def export_data_async(self, format=None, **kwargs):
        format = format or self.default_format
        download = DownloadBase()
        download.set_task(couchexport.tasks.export_async.delay(
            self,
            download.download_id,
            format=format,
            **kwargs
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
        first_row = list(list(tables)[0])[1]
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
        return get_export_components(self.index, previous_export_id, filter=self.filter & filter)

    def get_export_files(self, format='', previous_export_id=None, filter=None,
                         use_cache=True, max_column_size=2000, separator='|', process=None, **kwargs):
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

    is_safe = BooleanProperty(default=False)
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

    def transform(self, doc):
        return doc

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
            if self.tables_by_index.has_key(index):
                return list(self.tables_by_index[index].get_column_configuration(self.schema))
            else:
                return [ExportColumn(index=c, display=c).to_config_format(selected=False) for c in self.schema.get_columns(index)]

        def display():
            if self.tables_by_index.has_key(index):
                return self.tables_by_index[index].display
            else:
                return index

        return {
            "index": index,
            "display": display(),
            "column_configuration": column_configuration(),
            "selected": index in self.tables_by_index
        }
    
    def get_table_headers(self, override_name=False):
        return ((self.table_name if override_name and i==0 else t.index, [t.get_headers_row()]) for i, t in enumerate(self.tables))
        
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
        self.set_schema(build_latest_schema(self.index))
        
    def set_schema(self, schema):
        """
        Set the schema for this object.
        
        Does NOT save the doc, just updates the in-memory object.
        """
        self.schema_id = schema.get_id
    
    def trim(self, document_table, doc, apply_transforms=True):
        for table_index, data in document_table:
            if self.tables_by_index.has_key(table_index):
                # todo: currently (index, rows) instead of (display, rows); where best to convert to display?
                yield (table_index, self.tables_by_index[table_index].trim(data, doc, apply_transforms))

    def get_export_components(self, previous_export_id=None, filter=None):
        from couchexport.export import ExportConfiguration

        database = get_db()

        config = ExportConfiguration(database, self.index,
            previous_export_id,
            self.filter & filter)

        # get and checkpoint the latest schema
        updated_schema = config.get_latest_schema()
        export_schema_checkpoint = ExportSchema(seq=config.current_seq,
            schema=updated_schema,
            index=config.schema_index)
        export_schema_checkpoint.save()

        return config, updated_schema, export_schema_checkpoint
    
    def get_export_files(self, format=None, previous_export=None, filter=None, process=None, max_column_size=None, apply_transforms=True, **kwargs):
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
            if self.transform and apply_transforms:
                doc = self.transform(doc)
            formatted_tables = self.trim(
                format_tables(
                    create_intermediate_tables(doc, updated_schema),
                    separator="."
                ),
                doc,
                apply_transforms=apply_transforms
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

    def to_export_config(self):
        """
        Return an ExportConfiguration object that represents this.
        """
        # confusingly, the index isn't the actual index property,
        # but is the index appended with the id to this document.
        # this is to avoid conflicts among multiple exports
        index = "%s-%s" % (self.index, self._id) if isinstance(self.index, basestring) else \
            self.index + [self._id] # self.index required to be a string or list
        return ExportConfiguration(index=index, name=self.name,
                                   format=self.default_format)

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
    def saved_exports(self):
        if not hasattr(self, "_saved_exports"):
            self._saved_exports = \
                [(export_config, 
                  SavedBasicExport.view("couchexport/saved_exports", 
                                        key=json.dumps(export_config.index),
                                        include_docs=True,
                                        reduce=False).one()) \
                 for export_config in self.all_configs]
        return self._saved_exports

    @property
    def all_configs(self):
        """
        Return an iterator of config-like objects that include the
        main configs + the custom export configs.
        """
        for full in self.full_exports:
            yield full
        for custom in self.get_custom_exports():
            yield custom.to_export_config()

    @property
    def all_export_schemas(self):
        """
        Return an iterator of ExportSchema-like objects that include the 
        main configs + the custom export configs.
        """
        for full in self.full_exports:
            yield FakeSavedExportSchema(index=full.index)
        for custom in self.get_custom_exports():
            yield custom

    @property
    def all_exports(self):
        """
        Returns an iterator of tuples consisting of the export config
        and an ExportSchema-like document that can be used to get at
        the data.
        """
        return zip(self.all_configs, self.all_export_schemas)

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
