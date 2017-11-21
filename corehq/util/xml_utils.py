from __future__ import absolute_import
from decimal import Decimal
from xml.dom import minidom
import datetime
from dimagi.utils.parsing import json_format_datetime
import six


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
    elif isinstance(value, (int, Decimal, float, long)):
        return six.text_type(value)
    else:
        return value if value is not None else ""


def indent_xml(xml_string):
    """
    Takes an xml string and returns an indented and properly tabbed version of the string
    """
    if isinstance(xml_string, six.text_type):
        xml_string = xml_string.encode('utf-8')
    return minidom.parseString(xml_string).toprettyxml()
