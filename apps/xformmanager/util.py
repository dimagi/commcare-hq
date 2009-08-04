import re, os, tempfile, zipfile
import logging
import inspect
from lxml import etree

from django.core.servers.basehttp import FileWrapper
from django.db import connection
from django.http import HttpResponse, HttpResponseBadRequest
from transformers.csv import format_csv
from xformmanager.models import FormDefModel, ElementDefModel

MAX_MYSQL_TABLE_NAME_LENGTH = 64
MAX_PREFIX_LENGTH= 7
MAX_LENGTH = MAX_MYSQL_TABLE_NAME_LENGTH - MAX_PREFIX_LENGTH

def table_name(name):
    r = re.match('http://[a-zA-Z\.]+/(?P<tail>.*)', name)
    if r:
        tail = r.group('tail')
        if tail: 
            return "schema_" + sanitize(tail)
    return "schema_" + sanitize(name)
def old_table_name(name):
    return "x_" + _old_sanitize(name)
def _old_sanitize(name):
    _TABLE_PREFIX = "x_"
    _MAX_LENGTH = 64 - len(_TABLE_PREFIX)
    start = 0
    if len(name) >= _MAX_LENGTH:
        start = len(name)-_MAX_LENGTH
    truncated_name = name[start:len(name)]
    sanitized_name = truncated_name.replace("-","_").replace("/","_").replace(":","").replace(".","_").lower()
    if sanitized_name.lower() == "where" or sanitized_name.lower() == "when":
        return "_" + sanitized_name
    return sanitized_name
# this is purely for backwards compatibility
possible_naming_functions=[old_table_name,table_name]

def create_table_name(name):
    # current hack, fix later: 122 is mysql table limit, i think
    return table_name( name )

def retrieve_table_name(name):
    # current hack, fix later: 122 is mysql table limit, i think
    for func in possible_naming_functions:
        table_name = func(name)
        if ElementDefModel.objects.filter(table_name=table_name):
            return table_name
    return None

from django.db import connection
def table_exists( table_name):
    query = "select * from " + table_name + " limit 1";
    cursor = connection.cursor()
    try:
        cursor.execute(query)
    except:
        return False
    return True

def get_xml_string(stream_pointer):
    # formerly 'skip-junk'
    c = ''
    c = stream_pointer.read(1)
    count = 0
    while c != '<' and c != '':
        count = count + 1
        c = stream_pointer.read(1)
    if c == '':
        logging.error("Poorly formatted schema")
        return
    return "<" + stream_pointer.read()

# todo: put all sorts of useful db fieldname sanitizing stuff in here
def sanitize(name):
    # Accordin to the django documentation, this function should provide all the sanitation we need
    # In practice, all this function does is add quotes =b
    # return backend.DatabaseOperations().quote_name(name)
    start = 0
    if len(name) >= MAX_LENGTH:
        start = len(name)-MAX_LENGTH
    truncated_name = name[start:len(name)]
    sanitized_name = truncated_name.replace("-","_").replace("/","_").replace(":","").replace(".","_").lower()
    if sanitized_name.lower() == "where" or sanitized_name.lower() == "when":
        return "_" + sanitized_name
    return sanitized_name
    
#temporary measure to get target form
# todo - fix this to be more efficient, so we don't parse the file twice
def get_table_name(stream):
    try:
        logging.debug("Trying to parse xml_file")
        tree=etree.parse(stream)
        root=tree.getroot()
        logging.debug("Parsing xml file successful")
        logging.debug("Find xmlns from " + root.tag)
        #todo - add checks in case we don't have a well-formatted xmlns
        r = re.search('{[a-zA-Z0-9_\-\.\/\:]*}', root.tag)
        if r is None:
            logging.error( "NO NAMESPACE FOUND" )
            return None
        table_name = retrieve_table_name( r.group(0).strip('{').strip('}') )
        logging.debug( "Table name is " + unicode(table_name) )
        return table_name
    except etree.XMLSyntaxError:
        # this is probably just some non-xml data.
        # not a big deal, just don't return an xmlns
        return None
def get_target_namespace(stream):
    tree = etree.parse(stream)
    root = tree.getroot()
    return root.get('targetNamespace')

        
def formatted_join(parent_name, child_name):
    if parent_name: 
        # remove this hack later
        if parent_name.lower() != child_name.lower():
            return (str(parent_name) + "_" + str(child_name)).lower()
    return str(child_name).lower()

def join_if_exists(parent_name, child_name):
    if parent_name: 
        # remove this hack later
        return str(parent_name) + "_" + str(child_name)
    return str(child_name)

def get_csv_from_form(formdef_id, form_id=0, filter=''):
    try:
        xsd = FormDefModel.objects.get(id=formdef_id)
    except FormDefModel.DoesNotExist:
        return HttpResponseBadRequest("Schema with id %s not found." % formdef_id)
    cursor = connection.cursor()
    row_count = 0
    if form_id == 0:
        try:
            query= 'SELECT * FROM ' + xsd.form_name
            if filter: query = query + " WHERE " + filter
            query = query + ' ORDER BY id'
            cursor.execute(query)
        except Exception, e:
            return HttpResponseBadRequest(\
                "Schema %s could not be queried with query %s" % \
                ( xsd.form_name,query) )        
        rows = cursor.fetchall()
    else:
        try:
            cursor.execute("SELECT * FROM " + xsd.form_name + ' where id=%s', [form_id])
        except Exception, e:
            return HttpResponseBadRequest(\
                "Instance with id %s for schema %s not found." % (form_id,xsd.form_name) )
        rows = cursor.fetchone()
        row_count = 1
    columns = xsd.get_column_names()    
    name = xsd.form_name
    return format_csv(rows, columns, name, row_count)

def get_zipfile(file_list):
    """
    Create a ZIP file on disk and transmit it in chunks of 8KB,                 
    without loading the whole file into memory.                                    
    """
    temp = tempfile.TemporaryFile()
    archive = zipfile.ZipFile(temp, 'w', zipfile.ZIP_DEFLATED)
    for file in file_list:
        file = file.encode("utf-8")
        archive.write(file, os.path.basename(file))
    archive.close()
    wrapper = FileWrapper(temp)
    response = HttpResponse(wrapper, content_type='application/zip')
    response['Content-Disposition'] = 'attachment; filename=test.zip'
    response['Content-Length'] = temp.tell()
    temp.seek(0)
    return response
