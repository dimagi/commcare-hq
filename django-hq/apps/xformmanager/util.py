import re, os
import logging
from lxml import etree

TABLE_PREFIX = "x_"
MAX_LENGTH = 64 - len(TABLE_PREFIX)

def skip_junk(stream_pointer):
    """ This promises to be a useful file """
    c = ''
    while c != '<' and c != '':
        c = stream_pointer.read(1)
    if c == '':
        logging.error("Poorly formatted schema")
        return
    stream_pointer.seek(-1,os.SEEK_CUR)

def get_table_name(name):
    # check for uniqueness!
    # current hack, fix later: 122 is mysql table limit, i think
    table_name = sanitize(name)
    return TABLE_PREFIX + table_name

# todo: put all sorts of useful db fieldname sanitizing stuff in here
def sanitize(name):
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
    logging.debug("Trying to parse xml_file")
    skip_junk(stream)
    tree = etree.parse(stream)
    root = tree.getroot()
    logging.debug("Parsing xml file successful")
    logging.debug("Find xmlns from " + root.tag)
    #todo - add checks in case we don't have a well-formatted xmlns
    r = re.search('{[a-zA-Z0-9_\.\/\:]*}', root.tag)
    if r is None:
        logging.error( "NO NAMESPACE FOUND" )
        return None
    xmlns = get_table_name( r.group(0).strip('{').strip('}') )
    logging.debug( "Xmlns is " + xmlns )
    return xmlns

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
