
from lxml import etree

def xmlify(object_):
    root = _xmlify(object_)
    return etree.tostring(root, pretty_print=True)

def _xmlify(object_):
    """ a generic Python function to take a python object
    and serialize it as XML. Note that the output is entirely 
    dependent on the data structure of the input - which makes this 
    function useful for xmlifying a variety of python objects.
    However, if we want to customize the xml output format at any time,
    we can always drop in a different type of XMLify-er to 
    reporters/api_/resources.py
    
    understands: python objects, strings, tuples, + dictionaries of basic types
    plus lists of either basic types or any of the above
    
    """
    # end-condition: when we receive a tuple or a custom object
    if isinstance( object_, tuple):
        # the first element of tuple is attribute
        # the second is text
        root = etree.Element( 'entry', index=sanitize_value(unicode(object_[0])) )
        root.text=unicode(object_[1])
    else:
        root = etree.Element( sanitize_name(str(type(object_))) )
        for i in object_.__dict__:
            i_val = getattr(object_,i)
            if isinstance(i_val, basestring):
                # set strings to be attributes
                root.set(sanitize_name(i),sanitize_value(i_val) )
            elif isinstance( i_val, list):
                # i = string name of field
                # i_val = actual field value
                children = etree.Element( pluralize(i) )
                for val in i_val:
                    child = _xmlify(val)
                    children.append(child)
                root.append(children)
            elif isinstance( i_val, dict):
                # i = string name of field
                # i_val = actual field value
                children = etree.Element( pluralize(i) )
                for key in i_val.keys():
                    child = etree.etree.Element( sanitize_name(i) , name=sanitize_value(key), value=sanitize_value(i_val[key]) )
                    children.append(child)
                root.append(children)
            else:
                # set custom data structures to child elements
                child = _xmlify(i)
                root.append(child)
    return root

def pluralize(string):
    return string

def sanitize_name(string):
    value_sanitized = sanitize_value(string)
    name_sanitized = value_sanitized.replace("/","_").replace(" ","_").replace("-","_")
    return name_sanitized

def sanitize_value(string):
    sanitized = string.replace("<","_").replace(">","_").replace("'","_").replace(":","").replace(".","_")
    stripped = sanitized.strip('_')
    tail = stripped.rsplit('_',1)[-1]
    return tail
