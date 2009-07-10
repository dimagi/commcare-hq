import re, os
import logging
import inspect
#import xformmanager.reports.custom as custom_reports

from lxml import etree

#from django.db import backend

TABLE_PREFIX = "x_"
MAX_LENGTH = 64 - len(TABLE_PREFIX)

def skip_junk(stream_pointer):
    pass
    c = ''
    c = stream_pointer.read(1)
    count = 0
    while c != '<' and c != '':
        c = stream_pointer.read(1)
        count = count + 1
    if c == '':
        logging.error("Poorly formatted schema")
        return
    stream_pointer.seek(count)

def get_table_name(name):
    # check for uniqueness!
    # current hack, fix later: 122 is mysql table limit, i think
    table_name = sanitize(name)
    return TABLE_PREFIX + table_name

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
def get_xmlns(stream):
    try:
        logging.debug("Trying to parse xml_file")
        skip_junk(stream)
        tree = etree.parse(stream)
        root = tree.getroot()
        logging.debug("Parsing xml file successful")
        logging.debug("Find xmlns from " + root.tag)
        #todo - add checks in case we don't have a well-formatted xmlns
        r = re.search('{[a-zA-Z0-9_\-\.\/\:]*}', root.tag)
        if r is None:
            logging.error( "NO NAMESPACE FOUND" )
            return None
        xmlns = get_table_name( r.group(0).strip('{').strip('}') )
        logging.debug( "Xmlns is " + xmlns )
        return xmlns
    except etree.XMLSyntaxError:
        # this is probably just some non-xml data.
        # not a big deal, just don't return an xmlns
        return None
def get_target_namespace(stream):
    skip_junk(stream)
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
        return Nonen
#    if hasattr(custom_reports, domain.name):
#        return getattr(custom_reports, domain.name)()
#    return None

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
        # other fields defined in the custom class
        if is_mod_function(report_module, obj):
            obj_rep = {"name" : obj.func_name,
                       "display_name" : obj.__doc__   
                       } 
            to_return.append(obj_rep)
    return to_return
