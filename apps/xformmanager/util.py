import re, os
import logging
import inspect
from lxml import etree
from datetime import datetime

from django.db import connection
from django.http import HttpResponse, HttpResponseBadRequest

from transformers.csv import format_csv


MAX_MYSQL_TABLE_NAME_LENGTH = 64
MAX_PREFIX_LENGTH= 7
MAX_LENGTH = MAX_MYSQL_TABLE_NAME_LENGTH - MAX_PREFIX_LENGTH

def format_table_name(name, version=None, domain_name=None, prefix="schema_"):
    """Get rid of the leading 'http://dev.commcarehq.org/' or whatever host 
       at the start of the xmlns, to generate a table."""
    # NOTE: we may actually want these namespaces to make it to our table 
    # names eventually, though they are too long at the moment.
    r = re.match('http://[a-zA-Z\.]+/(?P<tail>.*)', name)
    if r:
        tail = r.group('tail')
        if tail: 
            # table prefix is appended after sanitation because
            # sanitation truncates to MAX_LENGTH minus len(prefix)
            name = tail
    if version:
        name = "%s_%s" % ( name, version )
    if domain_name:
        prefix = "%s%s_" % (prefix, domain_name)
    return ("%s%s" % (prefix, sanitize(name))).lower()

def table_exists( table_name):
    """Returns whether a table exists."""
    query = "select * from " + table_name + " limit 1";
    cursor = connection.cursor()
    try:
        cursor.execute(query)
    except:
        return False
    return True

# can flesh this out or integrate with other functions later
def format_field(model, name, value):
    """ should handle any sort of conversion for 'meta' field values """
    if value is None: return value
    t = type( getattr(model,name) )
    if t == datetime:
        return value.replace('T',' ')
    return value

def get_xml_string(stream_pointer):
    """This function checks for valid xml in a stream
       and skips bytes until it hits something that looks like
       xml. In general, this 'skipping' should never be used, as
       we expect to see well-formed XML from the server.
    
       stream_pointer: input stream
       returns: string of xml
    
    """
    # This function avoid stream_pointer.seek() for the vast majority
    # of cases (when xml is formatted correctly) just because i don't
    # like using 'seek' (never know when you're getting non-rewindable 
    # streams
    c = stream_pointer.read(1)
    count = 0
    while c != '<' and c != '':
        count = count + 1
        c = stream_pointer.read(1)
    if c == '':
        stream_pointer.seek(0)
        logging.error("Poorly formatted schema - no '<' found", \
                      extra={'xml':stream_pointer.read()})
        return
    xml_string = "<" + stream_pointer.read()
    if count > 0:
        stream_pointer.seek(0)
        logging.error("Poorly formatted schema", \
                      extra={'xml':stream_pointer.read()}) 
    return xml_string

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

def case_insensitive_iter(data_tree, tag):
    """ An iterator for lxml etree which is case-insensitive """
    if tag == "*":
        tag = None
    if tag is None or data_tree.tag.lower() == tag.lower():
        yield data_tree
    for d in data_tree: 
        for e in case_insensitive_iter(d,tag):
            yield e 

def get_unique_value(query_set, field_name, value):
    """Gets a unique name for an object corresponding to a particular
       django query.  Useful if you've defined your field as unique
       but are system-generating the values.  Starts by checking
       <value> and then goes to <value>_2, <value>_3, ... until 
       it finds the first unique entry. Assumes <value> is a string"""
    
    original_value = value
    column_count = query_set.filter(**{field_name: value}).count()
    to_append = 2
    while column_count != 0:
        value = "%s_%s" % (original_value, to_append)
        column_count = query_set.filter(**{field_name: value}).count()
        to_append = to_append + 1
    return value
                    
def get_sort_string(sort_column, sort_descending):
    """From a sort column and descending boolean, construct 
       a string that can be used in sql queries, e.g:
         ORDER BY <sort_column> <descending?>
       if sort_column is empty this returns an empty string"""
    if sort_column:
        sort_descending_string = "desc" if sort_descending else ""
        return " ORDER BY %s %s" % (sort_column, sort_descending_string) 
    return ""

def case_insensitive_attribute(lxml_element, attribute_name):
    # there must be a better way of finding case-insensitive attribute
    for i in lxml_element.attrib:
        if (i.lower()==attribute_name.lower()):
            return lxml_element.attrib[i]
