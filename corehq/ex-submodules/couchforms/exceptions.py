from django.conf import settings
from couchforms.const import MAGIC_PROPERTY, VALID_ATTACHMENT_FILE_EXTENSIONS


class CouchFormException(Exception):
    """
    A custom exception for the XForms application.
    """
    pass


class XMLSyntaxError(CouchFormException):
    pass


class MissingXMLNSError(CouchFormException):
    pass


class UnexpectedDeletedXForm(Exception):
    pass


class BadSubmissionRequest(Exception):
    def __init__(self, message, status_code=400):
        self.message = message
        self.status_code = status_code


class MultipartFilenameError(BadSubmissionRequest):
    def __init__(self):
        super().__init__(
            'If you use multipart/form-data, please name your file %s.\n'
            'You may also do a normal (non-multipart) post '
            'with the xml submission as the request body instead.\n' % MAGIC_PROPERTY
        )


class MultipartEmptyPayload(BadSubmissionRequest):
    def __init__(self):
        super().__init__(
            'If you use multipart/form-data, the file %s '
            'must not have an empty payload\n' % MAGIC_PROPERTY
        )


class EmptyPayload(BadSubmissionRequest):
    def __init__(self):
        super().__init__('Post may not have an empty body\n')


class PayloadTooLarge(BadSubmissionRequest):
    def __init__(self):
        super().__init__(
            "Form exceeds 10MB size limit\n",
            413
        )


class UnprocessableFormSubmission(BadSubmissionRequest):
    pass


class InvalidSubmissionFileExtensionError(UnprocessableFormSubmission):
    def __init__(self):
        super().__init__(
            "If you use multipart/form-data, please use xml file only for "
            "submitting form xml. You may also do a normal (non-multipart) "
            "with the xml submission as the request body instead\n",
            422
        )


class InvalidAttachmentFileError(UnprocessableFormSubmission):
    def __init__(self):
        super().__init__(
            "If you use multipart/form-data, please use the following "
            "supported file extensions for attachments: "
            f"{', '.join(VALID_ATTACHMENT_FILE_EXTENSIONS)}\n",
            422
        )


class AttachmentSizeTooLarge(BadSubmissionRequest):
    def __init__(self):
        super().__init__(
            f"Attachment exceeds {settings.MAX_UPLOAD_SIZE_ATTACHMENT/(1024*1024):,.0f}MB size limit\n",
            413
        )
