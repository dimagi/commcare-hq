from couchforms.const import MAGIC_PROPERTY


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
    def __init__(self, message):
        self.message = message


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
            'If you use multipart/form-data, the file %s'
            'must not have an empty payload\n' % MAGIC_PROPERTY
        )


class EmptyPayload(BadSubmissionRequest):
    def __init__(self):
        super().__init__('Post may not have an empty body\n')
