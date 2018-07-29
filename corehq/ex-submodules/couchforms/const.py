
from __future__ import unicode_literals
TAG_TYPE = "#type"
TAG_XML = "#xml"
TAG_VERSION = "@version"
TAG_UIVERSION = "@uiVersion"
TAG_NAMESPACE = "@xmlns"
TAG_NAME = "@name"

TAG_META = "meta"

TAG_FORM = 'form'

ATTACHMENT_NAME = "form.xml"

MAGIC_PROPERTY = 'xml_submission_file'

RESERVED_WORDS = [TAG_TYPE, TAG_XML, TAG_VERSION, TAG_UIVERSION, TAG_NAMESPACE,
                  TAG_NAME, TAG_META, ATTACHMENT_NAME, 'case', MAGIC_PROPERTY]


class BadRequest(object):

    def __init__(self, message):
        self.message = message


MULTIPART_FILENAME_ERROR = BadRequest((
    'If you use multipart/form-data, please name your file %s.\n'
    'You may also do a normal (non-multipart) post '
    'with the xml submission as the request body instead.\n'
) % MAGIC_PROPERTY)
MULTIPART_EMPTY_PAYLOAD_ERROR = BadRequest((
    'If you use multipart/form-data, the file %s'
    'must not have an empty payload\n'
) % MAGIC_PROPERTY)
EMPTY_PAYLOAD_ERROR = BadRequest('Post may not have an empty body\n')

DEVICE_LOG_XMLNS = 'http://code.javarosa.org/devicereport'
