from lxml import etree as ElementTree, etree
from django.http import HttpResponse
from django.utils.translation import gettext_lazy as _
import six

RESPONSE_XMLNS = 'http://openrosa.org/http/response'


class ResponseNature(object):
    """
    A const holding class for different response natures
    """
    # See https://confluence.dimagi.com/display/commcarepublic/Submission+API
    SUBMIT_SUCCESS = 'submit_success'
    SUBMIT_ERROR = 'submit_error'
    PROCESSING_FAILURE = 'processing_failure'
    POST_PROCESSING_FAILURE = 'post_processing_failure'

    OTA_RESTORE_SUCCESS = 'ota_restore_success'
    OTA_RESTORE_PENDING = 'ota_restore_pending'
    OTA_RESTORE_ERROR = 'ota_restore_error'


def get_response_element(message, nature=''):
    return OpenRosaResponse(message, nature, status=None).etree()


def get_simple_response_xml(message, nature=''):
    return OpenRosaResponse(message, nature, status=None).xml()


def get_openrosa_reponse(message, nature, status):
    return OpenRosaResponse(message, nature, status).response()


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
        elem.set('xmlns', RESPONSE_XMLNS)
        msg_elem = ElementTree.Element('message')
        if self.nature:
            msg_elem.set('nature', self.nature)
        msg_elem.text = six.text_type(self.message)
        elem.append(msg_elem)
        return elem

    def xml(self):
        return ElementTree.tostring(self.etree(), encoding='utf-8')

    def response(self):
        return HttpResponse(self.xml(), status=self.status)


def get_openarosa_success_response(message=None):
    if not message:
        message = _('   √   ')
    return get_openrosa_reponse(message, ResponseNature.SUBMIT_SUCCESS, 201)

SUBMISSION_IGNORED_RESPONSE = get_openrosa_reponse(
    '√ (this submission was ignored)', ResponseNature.SUBMIT_SUCCESS, 201
)
BLACKLISTED_RESPONSE = get_openrosa_reponse(
    message=(
        "This submission was blocked because of an unusual volume "
        "of submissions from this project space.  Please contact "
        "support to resolve."
    ),
    nature=ResponseNature.SUBMIT_ERROR,
    status=509,
)


def parse_openrosa_response(response):
    """Parse an OpenRosaResponse from the response XML.
    :returns: OpenRosaResponse object or None"""
    try:
        root = etree.fromstring(response)
    except etree.XMLSyntaxError:
        return

    message = root.find(f'{{{RESPONSE_XMLNS}}}message')
    if message is None:
        return

    return OpenRosaResponse(message.text.strip(), message.get("nature"), None)
