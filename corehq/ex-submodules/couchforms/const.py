from abc import ABC

from django.http import HttpResponse, HttpResponseBadRequest


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


SUPPORTED_MEDIA_FILE_EXTENSIONS = [
    "jpg", "jpeg", "3gpp", "3gp", "3ga", "3g2", "mp3", "wav", "amr",
    "mp4", "3gp2", "mpg4", "mpeg4", "m4v", "mpg", "mpeg", "qcp", "ogg"
]
PERMITTED_FORM_SUBMISSION_FILE_EXTENSIONS = ['xml']


class InvalidRequest(ABC):
    def __init__(self, message):
        self.message = message

    def response(self):
        raise NotImplementedError()


class BadRequest(InvalidRequest):
    def response(self):
        return HttpResponseBadRequest(self.message)


class UnprocessableRequest(InvalidRequest):
    def response(self):
        return HttpResponse(self.message, status=422)


MULTIPART_FILENAME_ERROR = BadRequest((
    'If you use multipart/form-data, please name your file %s.xml.\n'
    'You may also do a normal (non-multipart) post '
    'with the xml submission as the request body instead.\n'
) % MAGIC_PROPERTY)
MULTIPART_INVALID_SUBMISSION_FILE_EXTENSION_ERROR = UnprocessableRequest((
    'If you use multipart/form-data, please use xml file only for submitting form xml.\n'
    'You may also do a normal (non-multipart) post '
    'with the xml submission as the request body instead.\n'
))
MULTIPART_INVALID_ATTACHMENT_FILE_EXTENSION_ERROR = UnprocessableRequest(
    "If you use multipart/form-data, please use the following supported file extensions for attachments:\n"
    f"{', '.join(SUPPORTED_MEDIA_FILE_EXTENSIONS)}"
)
MULTIPART_EMPTY_PAYLOAD_ERROR = BadRequest((
    'If you use multipart/form-data, the file %s'
    'must not have an empty payload\n'
) % MAGIC_PROPERTY)
EMPTY_PAYLOAD_ERROR = BadRequest('Post may not have an empty body\n')

DEVICE_LOG_XMLNS = 'http://code.javarosa.org/devicereport'
