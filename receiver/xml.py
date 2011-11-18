from __future__ import absolute_import
from xml.etree import ElementTree

RESPONSE_XMLNS = "http://openrosa.org/http/response"

# Response template according to 
# https://bitbucket.org/javarosa/javarosa/wiki/OpenRosaRequest


def get_response_element(message):
    elem = ElementTree.Element("OpenRosaResponse")
    elem.attrib = {"xmlns": RESPONSE_XMLNS }
    msg_elem = ElementTree.Element("message")
    msg_elem.text = unicode(message)
    elem.append(msg_elem)
    return elem
    
def get_simple_response_xml(message):
    return ElementTree.tostring(get_response_element(message), encoding="utf-8")
