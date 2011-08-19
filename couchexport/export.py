from couchexport.schema import get_docs, get_schema
import csv
import zipfile
from StringIO import StringIO
from django.conf import settings
from couchexport.models import ExportSchema, Format, SavedExportSchema
from couchdbkit.client import Database
import re
from dimagi.utils.mixins import UnicodeMixIn

        
def get_full_export_tables(schema_index, previous_export, filter=None):
    """
    Returns a tuple, the first element being the tabular data ready for 
    processing, and the second the saved checkpoint associated with the tables.
    
    The "filter" argument allows you to pass in a function to filter documents
    from the results. The filter function should take in a document and return
    true if the document should be included, otherwise false.
    """
    db = Database(settings.COUCH_DATABASE)
    
    # used cached export config to determine doc list
    # previous_export = ExportSchema.last(schema_index)
    current_seq = db.info()["update_seq"]
    docs = get_docs(schema_index, previous_export, filter)
    if not docs:
        return (None, None)
    
    checkpoint = ExportSchema.last(schema_index)
    if not previous_export and checkpoint:
        temp_docs = get_docs(schema_index, previous_export, filter)
        schema = get_schema(temp_docs, checkpoint)
    else:
        schema = get_schema(docs, previous_export)
    
    [schema_dict] = schema
    this_export = ExportSchema(seq=current_seq, schema=schema_dict, 
                               index=schema_index)
    this_export.save()
    return (format_tables(create_intermediate_tables(docs,schema)), this_export)
    
    

def export_from_tables(tables, file, format):
    if format == Format.CSV:
        _export_csv(tables, file)
    elif format == Format.XLS:
        _export_excel(tables).save(file)
    elif format == Format.XLS_2007:
        _export_excel_2007(tables).save(file)
    else:
        raise Exception("Unsupported export format: %s!" % format)
    
def export(schema_index, file, format=Format.XLS_2007, 
           previous_export_id=None, filter=None):
    """
    Exports data from couch documents matching a given tag to a file. 
    Returns true if it finds data, otherwise nothing
    """
    previous_export = ExportSchema.get(previous_export_id) \
                      if previous_export_id else None
    tables, checkpoint = get_full_export_tables(schema_index, previous_export, filter)
    if not tables:
        return None
    export_from_tables(tables, file, format)
    return checkpoint

class Constant(UnicodeMixIn):
    def __init__(self, message):
        self.message = message
    def __unicode__(self):
        return self.message
    
scalar_never_was = Constant("---")
list_never_was = Constant("this list never existed")

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
        raise Exception("doc-schema mismatch: %s" % msg)

    if schema is None:
        if doc:
            log("%s is not null" % doc)
        return None
    if isinstance(schema, list):
        if not doc:
            doc = []
        if not isinstance(doc, list):
            return fit_to_schema([doc], schema)
        answ = []
        schema_, = schema
        for doc_ in doc:
            answ.append(fit_to_schema(doc_, schema_))
        return answ
    if isinstance(schema, dict):
        if not doc:
            doc = {}
        doc_keys = set(doc.keys())
        schema_keys = set(schema.keys())
        if doc_keys - schema_keys:
            log("doc has keys not in schema: %s" % (', '.join(doc_keys - schema_keys)))
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


def create_intermediate_tables(docs, schema, integer='#'):
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
                column.append(k)
            else:
                table.extend(column)
                table.append(integer)
                column = []
                id.append(k)
        return (tuple(table), tuple(column), tuple(id))
    schema = [schema]
    docs = fit_to_schema(docs, schema)
    #first, flatten documents
    queue = [()]
    leaves = []
    while queue:
        path = queue.pop()
        d = lookup(docs, path)
        if isinstance(d, dict):
            for key in d:
                queue.append(path + (key,))
        elif isinstance(d, list):
            for i,_ in enumerate(d):
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

def nice(column_name):
    return "/".join(column_name)

def format_tables(tables, id_label='id', separator='.'):
    answ = []
    for table_name, table in sorted(tables.items()):
        new_table = []
        keys = sorted(table.items()[0][1].keys()) # the keys for every row are the same
        header = [id_label]
        for key in keys:
            header.append(separator.join(key))
        new_table.append(header)
        for id, row in sorted(table.items()):
            new_row = []
            new_row.append(separator.join(map(unicode,id)))
            for key in keys:
                new_row.append(row[key])
            new_table.append(new_row)
        answ.append((separator.join(table_name), new_table))
    return answ

def _export_csv(tables, file):
    #temp = tempfile.TemporaryFile()
    temp = file
    archive = zipfile.ZipFile(temp, 'w', zipfile.ZIP_DEFLATED)
    
    # write forms
    used_names = []
    for table_name, table in tables:
        table_name_truncated = _clean_name(_next_unique(table_name, used_names))
        used_names.append(table_name_truncated)
        table_file = StringIO()
        writer = csv.writer(table_file, dialect=csv.excel)
        for row in table:
            for i, val in enumerate(row):
                if isinstance(val, unicode):
                    row[i] = val.encode("utf8")
            writer.writerow(row)
        archive.writestr("%s.csv" % table_name_truncated, table_file.getvalue())
        
    archive.close()
    temp.seek(0)
    return temp

    
def _export_excel(tables):
    try:
        import xlwt
    except ImportError:
        raise Exception("It doesn't look like this machine is configured for "
                        "excel export. To export to excel you have to run the "
                        "command:  easy_install xlutils")
    book = xlwt.Workbook()
    used_names = []
    for table_name, table in tables:
        # this is in case the first 20 characters are the same, but we	
        # should do something smarter.	
        table_name_truncated = _next_unique(table_name, used_names, 20)
        used_names.append(table_name_truncated)
        sheet = book.add_sheet(_clean_name(table_name_truncated))
        for i,row in enumerate(table):
            for j,val in enumerate(row):
                sheet.write(i,j,unicode(val))
    return book

def _export_excel_2007(tables):
    try:
        import openpyxl
    except ImportError:
        raise Exception("It doesn't look like this machine is configured for "
                        "excel export. To export to excel you have to run the "
                        "command:  easy_install openpyxl")
    book = openpyxl.workbook.Workbook()
    book.remove_sheet(book.worksheets[0])
    used_names = []
    for table_name, table in tables:
        # this is in case the first 20 characters are the same, but we    
        # should do something smarter.    
        table_name_truncated = _next_unique(table_name, used_names, 31)
        used_names.append(table_name_truncated)
        sheet = book.create_sheet()
        sheet.title = _clean_name(table_name_truncated)
        for i,row in enumerate(table):
            # the docs claim this should work but the source claims it doesn't 
            #sheet.append(row) 
            for j,val in enumerate(row):
                sheet.cell(row=i,column=j).value = unicode(val)
    return book


def _clean_name(name):
    return re.sub(r"[[\\?*/:\]]", "-", name)
    
def _next_unique(string, reserved_strings, max_len=500):
    counter = 1
    if len(string) > max_len:
        # truncate from the beginning since the end has more specific information
        string = string[-max_len:] 
    orig_string = string
    while string in reserved_strings:
        string = "%s%s" % (orig_string, counter)
        if len(string) > max_len:
            counterlen = len(str(counter))
            string = "%s%s" % (orig_string[-(max_len - counterlen):], counter)
        counter = counter + 1
    return string
    
