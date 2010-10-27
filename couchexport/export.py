from couchdbkit.client import Database
from django.conf import settings
import hashlib

def export_excel(schema_index, file):
    """
    Exports data from couch documents matching a given tag to a file. 
    Returns true if it finds data, otherwise nothing
    """
    db = Database(settings.COUCH_DATABASE)
    schema_row = db.view('couchexport/schema', key=schema_index, group=True).one()
    if not schema_row: return None
    schema = schema_row['value']
    docs = [result['value'] for result in db.view("couchexport/schema_index", key=schema_index).all()]
    tables = format_tables(create_intermediate_tables(docs,schema))
    _export_excel(tables).save(file)
    return True

class Constant(object):
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
import csv
import xlwt

def export_csv(tables):
    "this function isn't ready to use because of how it deals with files"
    for table_name, table in tables:
        writer = csv.writer(open("csv_test/" + table_name+'.csv', 'w'), dialect=csv.excel)
        for row in table:
            writer.writerow([x if '"' not in x else "" for x in row])

def _export_excel(tables):
    book = xlwt.Workbook()
    for table_name, table in tables:
        #test hack
        #sheet = book.add_sheet(table_name[-20:])
        hack_table_name_prefix = table_name[-20:]
        hack_table_name = hack_table_name_prefix[0:10] + hashlib.sha1(table_name).hexdigest()[0:10]
        sheet = book.add_sheet(hack_table_name)
        for i,row in enumerate(table):
            for j,val in enumerate(row):
                sheet.write(i,j,unicode(val))
    return book


