from __future__ import absolute_import
from xml.etree import ElementTree


def get_payload_content(payload):
    try:
        f = open(payload, 'r')
        return f.read()
    except IOError:
        return payload


def get_payload_etree(payload):
    try:
        return ElementTree.parse(payload)
    except IOError:
        return ElementTree.fromstring(payload)
