""" A singleton to process Python objects and spit out xml """
from lxml import etree

def xmlify(object_):
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
    root = _xmlify(object_)
    return etree.tostring(root, pretty_print=True)

def _xmlify(object_):
    # end-condition: when we receive a tuple or a custom object
    if isinstance( object_, tuple):
        # the first element of tuple is attribute
        # the second is text
        root = etree.Element( 'entry', index=_sanitize_text(unicode(object_[0])) )
        child = etree.Element( 'value' )
        child.text = unicode(object_[1])
        root.append(child)
    else:
        root = etree.Element( _sanitize_tag(str(type(object_))) )
        for i in object_.__dict__:
            i_val = getattr(object_,i)
            if isinstance(i_val, basestring):
                # set strings to be attributes
                root.set(_sanitize_tag(i),_sanitize_text(i_val) )
            elif isinstance( i_val, list):
                # i = string name of field
                # i_val = actual field value
                children = etree.Element( i )
                # some lists have names
                if hasattr(i_val,"__dict__"):
                    for i in i_val.__dict__:
                        value = getattr(i_val,i)
                        if isinstance(value, basestring):
                            # set strings to be attributes
                            children.set(_sanitize_tag(i),_sanitize_text(value) )
                for val in i_val:
                    child = _xmlify(val)
                    children.append(child)
                root.append(children)
            elif isinstance( i_val, dict):
                # i = string name of field
                # i_val = actual field value
                children = etree.Element( i )
                for key in i_val.keys():
                    child = etree.Element( _sanitize_tag(i) , name=_sanitize_text(key), value=_sanitize_text(i_val[key]) )
                    children.append(child)
                root.append(children)
            else:
                # set custom data structures to child elements
                child = _xmlify(i)
                root.append(child)
    return root

def _sanitize_tag(string):
    value_sanitized = _sanitize_text(string)
    name_sanitized = value_sanitized.replace("/","_").replace(" ","_").replace("-","_")
    return name_sanitized

def _sanitize_text(string):
    string = unicode(string)
    sanitized = string.replace("<","_").replace(">","_").replace("'","_").replace(":","").replace(".","_")
    stripped = sanitized.strip('_')
    tail = stripped.rsplit('_',1)[-1]
    return tail
