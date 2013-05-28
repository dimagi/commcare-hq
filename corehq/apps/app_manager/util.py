from corehq.apps.app_manager.xform import XForm, XFormError, parse_xml
import re

def get_app_id(form):
    """
    Given an XForm instance, try to grab the app id, returning
    None if not available. This is just a shortcut since the app_id
    might not always be set.
    """
    return getattr(form, "app_id", None)


def split_path(path):
    path_parts = path.split('/')
    name = path_parts.pop(-1)
    path = '/'.join(path_parts)
    return path, name

def save_xform(app, form, xml):
    try:
        xform = XForm(xml)
    except XFormError:
        pass
    else:
        duplicates = app.get_xmlns_map()[xform.data_node.tag_xmlns]
        for duplicate in duplicates:
            if form == duplicate:
                continue
            else:
                data = xform.data_node.render()
                xmlns = "http://openrosa.org/formdesigner/%s" % form.get_unique_id()
                data = data.replace(xform.data_node.tag_xmlns, xmlns, 1)
                xform.instance_node.remove(xform.data_node.xml)
                xform.instance_node.append(parse_xml(data))
                xml = xform.render()
                break
    form.source = xml

CASE_TYPE_REGEX = r'^[\w-]+$'
_case_type_regex = re.compile(CASE_TYPE_REGEX)

def is_valid_case_type(case_type):
    """
    >>> is_valid_case_type('foo')
    True
    >>> is_valid_case_type('foo-bar')
    True
    >>> is_valid_case_type('foo bar')
    False
    >>> is_valid_case_type('')
    False
    >>> is_valid_case_type(None)
    False
    """
    return bool(_case_type_regex.match(case_type or ''))
