import re, os
import logging
from lxml import etree

TABLE_PREFIX = "x_"

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
    MAX_LENGTH = 64 - len(TABLE_PREFIX)
    start = 0
    if len(name) >= MAX_LENGTH:
        start = len(name)-MAX_LENGTH
    sanitized_name = str(name[start:len(name)]).replace("/","_").replace(":","").replace(".","_").lower()
    return TABLE_PREFIX + sanitized_name

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
