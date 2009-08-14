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
    """ root is a special case just because there can be only one root """
    root = etree.Element( _sanitize_tag(str(type(object_))) )
    if hasattr(object_,"__dict__"):
        for i in object_.__dict__:
            i_val = getattr(object_,i)
            if isinstance(i_val, basestring):
                # set strings to be attributes
                root.set(_sanitize_tag(i),_sanitize_text(i_val) )
            elif isinstance( i_val, list):
                # for lists in root, we don't need to create child elements
                # (because we already have 'root')
                for val in i_val:
                    _inner_xmlify(val, root)
            elif isinstance( i_val, dict):
                # i = string name of field
                # i_val = actual field value
                children = etree.Element( i )
                for key in i_val.keys():
                    child = etree.Element( _sanitize_tag(i) , name=_sanitize_text(key), value=_sanitize_text(i_val[key]) )
                    children.append(child)
                root.append(children)
    return root

def _inner_xmlify(object_, parent, name=None):
    """ creates children xml elements and automatically adds them to parent """
    if name is None:
        # oddly enough 'unicode' is not as universal as 'str'
        name = _sanitize_tag(str(type(object_)))
    # end-condition: when we receive a tuple, list, or custom python object
    if isinstance( object_, tuple):
        # the first element of tuple is attribute, the second is text
        element = etree.Element( 'value', index=_sanitize_text(unicode(object_[0])) )
        element.text = unicode(object_[1])
        parent.append(element)
    elif isinstance( object_, list):
        element = etree.Element( name )
        if hasattr(object_,"__dict__"):
            for i in object_.__dict__:
                i_val = getattr(object_,i)
                if isinstance(i_val, basestring):
                    # set strings to be attributes
                    element.set(_sanitize_tag(i),_sanitize_text(i_val) )
                elif isinstance( i_val, dict):
                    # i = string name of field
                    # i_val = actual field value
                    children = etree.Element( i )
                    for key in i_val.keys():
                        child = etree.Element( _sanitize_tag(i) , name=_sanitize_text(key), value=_sanitize_text(i_val[key]) )
                        children.append(child)
                    element.append(children)
        for val in object_:
            _inner_xmlify(val, element)
        parent.append(element)
    else:
        # child is a python object
        element = etree.Element( name )
        if hasattr(object_,"__dict__"):
            for i in object_.__dict__:
                i_val = getattr(object_,i)
                if isinstance(i_val, basestring):
                    # set strings to be attributes
                    element.set(_sanitize_tag(i),_sanitize_text(i_val) )
                elif isinstance( i_val, list):
                    _inner_xmlify(i_val, element, i)
                elif isinstance( i_val, dict):
                    # i = string name of field
                    # i_val = actual field value
                    children = etree.Element( i )
                    for key in i_val.keys():
                        child = etree.Element( _sanitize_tag(i) , name=_sanitize_text(key), value=_sanitize_text(i_val[key]) )
                        children.append(child)
                    element.append(children)
                else:
                    # set custom data structures to child elements
                    _inner_xmlify(i, element)
        parent.append(element)

def _sanitize_tag(string):
    value_sanitized = _sanitize_text(string)
    name_sanitized = value_sanitized.replace("/","_").replace(" ","_").replace("-","_").lower()
    return name_sanitized

def _sanitize_text(string):
    string = unicode(string)
    sanitized = string.replace("<","_").replace(">","_").replace("'","_").replace(":","").replace(".","_")
    stripped = sanitized.strip('_')
    tail = stripped.rsplit('_',1)[-1]
    return tail
