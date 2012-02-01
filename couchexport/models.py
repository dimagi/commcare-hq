from couchdbkit.ext.django.schema import Document, IntegerProperty, DictProperty,\
    Property, DocumentSchema, StringProperty, SchemaListProperty, ListProperty,\
    StringListProperty
import json
from StringIO import StringIO
from couchexport import util
from dimagi.utils.mixins import UnicodeMixIn
from dimagi.utils.modules import try_import, to_function
from dimagi.utils.couch.database import get_db

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
        return dict([c.index, c.display] for c in self.columns)
    
    def get_column_configuration(self, schema):
        all_cols = schema.top_level_nodes
        cols = []
        for c in self.columns:
            cols += [{"index": c.index, "display": c.display, "selected": True}]
            all_cols = filter(lambda x: x != c.index, all_cols) # exclude
        cols += [{"index": c,
                 "display": self.col_dict[c] if c in self.col_dict else c,
                 "selected": c in self.col_dict} for c in all_cols]
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
            ret.append(FormattedRow([row_data[self._header_to_index_map[col]] for col in self._cols if col != "id"], id))
        return ret
    
class SavedExportSchema(Document, UnicodeMixIn):
    """
    Lets you save an export format with a schema and list of columns
    and display names.
    """
    name = StringProperty()
    default_format = StringProperty()
    index = JsonProperty() # this is stored duplicately in the schema, but is convenient
    schema_id = StringProperty()
    tables = SchemaListProperty(ExportTable)
    filter_function = StringProperty()
    
    def __unicode__(self):
        return "%s (%s)" % (self.name, self.index)
    
    _schema = None
    @property
    def schema(self):
        if self._schema is None:
            self._schema = ExportSchema.get(self.schema_id)
    
        return self._schema
    
    @property
    def filter(self):
        if self.filter_function:
            func = to_function(self.filter_function)
            #print "got filter function %s for %s" % (func, self.filter_function)
            return func
    
    @classmethod
    def default(cls, schema, name=""):
        return cls(name=name, index=schema.index, schema_id=schema.get_id,
                   tables=[ExportTable.default(schema.tables[0][0])])
        
    def get_table_configuration(self, index):
        table_dict = dict([t.index, t] for t in self.tables)
        return {"index": index, 
                "display": table_dict[index].display if index in table_dict else index,
                "column_configuration": table_dict[index].get_column_configuration(self.schema) \
                                            if index in table_dict else \
                                            [{"index": c, "display": c, 
                                              "selected": False} for c in self.schema.get_columns(index)],
                 "selected": index in table_dict} 
    
    def get_table_headers(self):
        return ((t.index, [t.get_headers_row()]) for t in self.tables)
        
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
    
    def download_data(self, format="", previous_export=None, filter=None):
        """
        If there is data, return an HTTPResponse with the appropriate data. 
        If there is not data returns None.
        """
        from couchexport.shortcuts import export_response
        from couchexport.export import get_writer, get_schema_new, \
            format_tables, create_intermediate_tables
        
        if not format:
            format = self.default_format or Format.XLS_2007
        
        from couchexport.export import ExportConfiguration
        database = get_db()
        config = ExportConfiguration(database, self.index, 
                                     previous_export, 
                                     util.intersect_filters(self.filter, filter))
        
        
        # get and checkpoint the latest schema
        updated_schema = get_schema_new(config)
        export_schema_checkpoint = ExportSchema(seq=config.current_seq, 
                                                schema=updated_schema,
                                                index=config.schema_index)
        export_schema_checkpoint.save()
        # transform docs onto output and save
        writer = get_writer(format)
        
        # open the doc and the headers
        formatted_headers = self.get_table_headers()
        tmp = StringIO()
        writer.open(formatted_headers, tmp)
        
        for doc in config.get_docs():
            writer.write(self.trim(format_tables\
                             (create_intermediate_tables(doc, updated_schema), 
                              separator=".")))
        writer.close()

        return export_response(tmp, format, self.name)

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
    
    
