from lxml.etree import Element, tostring

from ..utils import convert_xform_to_json

XML_PREFIX = '<?xml version="1.0" ?>\n'


def convert_form_to_xml(form_data):
    """Convert form data dict to XML string

    Does the inverse of `corehq.form_processor.utils.convert_xform_to_json()`

    See also: submodules/xml2json/xml2json/lib.py

    :param form_data: Form data dict: `<XFormInstance>.form_data`
    :returns: XML string
    :raises: ValueError if the input does not conform to expected
    conventions.
    :raises: RoundtripError if `convert_xform_to_json(xml)` produces a
    different result that than the given `form_data`.
    """
    tag = form_data.get("#type", "data")
    element = convert_json_to_xml(form_data, tag)
    xml = XML_PREFIX + tostring(element, pretty_print=True, encoding="unicode")
    if convert_xform_to_json(xml) != form_data:
        raise RoundtripError("to_json(to_xml(form_data)) != form_data")
    return xml


def convert_json_to_xml(data, tag):
    xml = Element(tag)
    for key, value in data.items():
        if key == "#text":
            xml.text = value
        elif key == "#type":
            if tag != value:
                raise ValueError(f"unexpected #type: {value!r} != {tag!r}")
        elif key.startswith("#"):
            raise ValueError(f"unknown hashtag: {key}")
        elif key.startswith("@"):
            xml.set(key[1:], validate_str(value))
        elif isinstance(value, dict):
            xml.append(convert_json_to_xml(value, key))
        elif isinstance(value, list):
            for item in value:
                xml.append(convert_json_to_xml(item, key))
        else:
            el = Element(key)
            el.text = validate_str(value)
            xml.append(el)
    return xml


def validate_str(value):
    if isinstance(value, str):
        return value
    raise ValueError(repr(value))


class RoundtripError(ValueError):
    pass
