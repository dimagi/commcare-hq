from __future__ import absolute_import
from xml.etree import ElementTree
from django.http import HttpResponse

RESPONSE_XMLNS = 'http://openrosa.org/http/response'


class ResponseNature(object):
    """
    A const holding class for different response natures
    """
    # not super decoupled having stuff related to submissions and user reg
    # here, but nice for this all to be in one place
    SUBMIT_SUCCESS = 'submit_success'
    SUBMIT_ERROR = 'submit_error'

    # users app
    SUBMIT_USER_REGISTERED = 'submit_user_registered'
    SUBMIT_USER_UPDATED = 'submit_user_updated'

    OTA_RESTORE_SUCCESS = 'ota_restore_success'
    OTA_RESTORE_ERROR = 'ota_restore_error'


def get_response_element(message, nature=''):
    return OpenRosaResponse(message, nature, status=None).etree()


def get_simple_response_xml(message, nature=''):
    return OpenRosaResponse(message, nature, status=None).xml()


class OpenRosaResponse(object):
    """
    Response template according to
    https://bitbucket.org/javarosa/javarosa/wiki/OpenRosaRequest

    """
    def __init__(self, message, nature, status):
        self.message = message
        self.nature = nature
        self.status = status

    def etree(self):
        elem = ElementTree.Element('OpenRosaResponse')
        elem.attrib = {'xmlns': RESPONSE_XMLNS}
        msg_elem = ElementTree.Element('message')
        if self.nature:
            msg_elem.attrib = {'nature': self.nature}
        msg_elem.text = unicode(self.message)
        elem.append(msg_elem)
        return elem

    def xml(self):
        return ElementTree.tostring(self.etree(), encoding='utf-8')

    def response(self):
        return HttpResponse(self.xml(), status=self.status)
