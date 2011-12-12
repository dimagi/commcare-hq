from couchdbkit.ext.django.schema import Document, IntegerProperty, DictProperty,\
    Property, DocumentSchema, StringProperty, SchemaListProperty, ListProperty
import json
from StringIO import StringIO
from couchexport import util
from dimagi.utils.mixins import UnicodeMixIn
from dimagi.utils.modules import try_import, to_function

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
            from couchexport.export import create_intermediate_tables, format_tables
            # this is some crazy hackery, but works. Essentially build the tables
            # for a (almost) totally blank set of documents
            full_tables = format_tables(create_intermediate_tables([{"_id": ""}],[self.schema]))
            self._tables = [(t[0], t[1][0]) for t in full_tables]
        return self._tables
    
    @property
    def table_dict(self):
        return dict(self.tables)
    
    @property
    def top_level_nodes(self):
        return self.tables[0][1]
    
    def get_columns(self, index):
        return self.table_dict[index]

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
    
    def format_data(self, data):
        
        headers = data[0]
        data = data[1:]
        header_to_index_map = dict([(h, i) \
                                    for i, h in enumerate(headers) \
                                    if h in self.col_dict])
        cols = map(lambda x: x.index, self.columns)
        headers = [self.col_dict[col] for col in cols]
        ret = [headers]
        for row in data:
            ret.append([row[header_to_index_map[col]] for col in cols])
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
    
    @property
    def table_configuration(self):
        return [self.get_table_configuration(index) \
                for index, cols in self.schema.tables]

    def get_export_tables(self, previous_export=None, filter=None):
        from couchexport.export import get_full_export_tables
        
        full_tables, checkpoint = get_full_export_tables\
                                    (self.index, previous_export, util.intersect_filters(self.filter, filter))
        if not full_tables: 
            return None
        
        table_dict = dict([t.index, t] for t in self.tables)
        trimmed_tables = []
        for table_index, data in full_tables:
            if table_index in table_dict:
                trimmed_tables.append((table_dict[table_index].display, 
                                       table_dict[table_index].format_data(data)))
        
        return trimmed_tables

    def download_data(self, format="", previous_export=None, filter=None):
        """
        If there is data, return an HTTPResponse with the appropriate data. 
        If there is not data returns None.
        """
        from couchexport.export import export_from_tables
        from couchexport.shortcuts import export_response
        
        if not format:
            format = self.default_format or Format.XLS_2007
        
        tables = self.get_export_tables(previous_export, filter=filter)
        if not tables:
            return None
        
        tmp = StringIO()
        export_from_tables(tables, tmp, format)
        return export_response(tmp, format, self.name)
