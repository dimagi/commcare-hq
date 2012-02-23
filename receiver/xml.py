from __future__ import absolute_import
from xml.etree import ElementTree

RESPONSE_XMLNS = "http://openrosa.org/http/response"

class ResponseNature(object):
    """
    A const holding class for different response natures
    """
    # not super decoupled having stuff related to submissions and user reg 
    # here, but nice for this all to be in one place
    SUBMIT_SUCCESS = "submit_success"
    SUBMIT_ERROR = "submit_error"
    
    # users app
    SUBMIT_USER_REGISTERED = "submit_user_registered"
    SUBMIT_USER_UPDATED = "submit_user_updated"
    
    OTA_RESTORE_SUCCESS = "ota_restore_success"
    OTA_RESTORE_ERROR = "ota_restore_error"

# Response template according to 
# https://bitbucket.org/javarosa/javarosa/wiki/OpenRosaRequest


def get_response_element(message, nature=""):
    elem = ElementTree.Element("OpenRosaResponse")
    elem.attrib = {"xmlns": RESPONSE_XMLNS }
    msg_elem = ElementTree.Element("message")
    if nature:
        msg_elem.attrib = {"nature": nature}
    msg_elem.text = unicode(message)
    elem.append(msg_elem)
    return elem
    
def get_simple_response_xml(message, nature=""):
    return ElementTree.tostring(get_response_element(message, nature),
                                encoding="utf-8")
