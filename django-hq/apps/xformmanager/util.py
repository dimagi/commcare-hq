import re, os
import logging
import inspect
from lxml import etree

from django.http import HttpResponseBadRequest
from django.db import connection
from transformers.csv_ import format_csv
from xformmanager.models import FormDefModel

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
    return "x_" + sanitize(name)
# this is purely for backwards compatibility
possible_naming_functions=[old_table_name,table_name]

def create_table_name(name):
    # current hack, fix later: 122 is mysql table limit, i think
    return table_name( name )

def retrieve_table_name(name):
    # current hack, fix later: 122 is mysql table limit, i think
    for func in possible_naming_functions:
        table_name = func(name)
        if table_exists( table_name ):
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

def is_mod_function(mod, func):
    '''Returns whether the object is a function in the module''' 
    return inspect.isfunction(func) and inspect.getmodule(func) == mod

def get_custom_report_module(domain):
    '''Get the reports module for a domain, if it exists.  Otherwise
       this returns nothing'''
    try:
        rep_module = __import__("xformmanager.reports.%s" % domain.name.lower(), 
                                fromlist=[''])
        return rep_module
    except ImportError:
        return None

def get_custom_reports(report_module):
    '''Given a reports module , get the list of custom reports defined
       in that class.  These are returned as dictionaries of the 
       following format:
         { "name" : function_name, "display_name" : function_doc }
       see reports/custom.py for more information 
    '''
    to_return = []
    for name in dir(report_module):
        obj = getattr(report_module, name)
        # using ismethod filters out the builtins and any 
        # other fields defined in the custom class.  
        # also use the python convention of keeping methods
        # that start with an "_" private.
        if is_mod_function(report_module, obj) and\
          not obj.func_name.startswith("_"):
            obj_rep = {"name" : obj.func_name,
                       "display_name" : obj.__doc__   
                       } 
            to_return.append(obj_rep)
    return to_return


