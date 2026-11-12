import datetime
from decimal import Decimal

from dimagi.utils.parsing import json_format_datetime
from lxml import etree


def serialize(value):
    """
    Serializes a value so it can properly be parsed into XML
    """
    if isinstance(value, datetime.datetime):
        return json_format_datetime(value)
    elif isinstance(value, datetime.date):
        return value.isoformat()
    elif isinstance(value, datetime.time):
        return value.strftime('%H:%M:%S')
    elif isinstance(value, (int, Decimal, float)):
        return str(value)
    else:
        return value if value is not None else ""


def indent_xml(xml_string):
    """
    Takes an xml string and returns an indented and properly tabbed version of the string
    """
    parsed = safe_fromstring(xml_string, remove_blank_text=True)
    etree.indent(parsed, space='\t')
    return etree.tostring(parsed, xml_declaration=True, encoding='UTF-8').decode('utf-8')


def get_safe_xml_parser(**kwargs):
    """
    Build a hardened ``lxml.etree.XMLParser``

    Additional keyword arguments are passed through to ``XMLParser`` for
    non-security options (e.g. ``remove_comments``, ``remove_blank_text``).
    Security-related options are fixed and may not be overridden.
    """
    return etree.XMLParser(**kwargs, **_SECURE_PARSER_KWARGS)


def safe_fromstring(xml_string, **parser_kwargs):
    """
    Parse an XML string into etree nodes using a hardened parser

    Additional keyword arguments are passed through to ``get_safe_xml_parser``.
    See ``lxml.etree.fromstring`` for usage documentation.
    """
    if isinstance(xml_string, str):
        xml_string = xml_string.encode('utf-8')
    return etree.fromstring(xml_string, parser=get_safe_xml_parser(**parser_kwargs))


# lxml.etree.XML is an alias of lxml.etree.fromstring, conventionally used
# for embedding XML literals rather than parsing arbitrary string input.
XML = safe_fromstring


_SECURE_PARSER_KWARGS = {
    # not XMLParser's default ('internal' is vulnerable to parameter-entity attack)
    'resolve_entities': False,

    # These match XMLParser defaults; locked here to prevent
    # accidental insecure parser configuration.
    'no_network': True,
    'load_dtd': False,
    'dtd_validation': False,
}
