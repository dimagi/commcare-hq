from dimagi.utils.mixins import UnicodeMixIn


class CouchFormException(Exception):
    """
    A custom exception for the XForms application.
    """
    pass


class XMLSyntaxError(CouchFormException):
    pass


class DuplicateError(CouchFormException):
    def __init__(self, xform):
        self.xform = xform


class UnexpectedDeletedXForm(Exception):
    pass


class SubmissionError(Exception, UnicodeMixIn):
    """
    When something especially bad goes wrong during a submission, this
    exception gets raised.
    """

    def __init__(self, error_log, *args, **kwargs):
        super(SubmissionError, self).__init__(*args, **kwargs)
        self.error_log = error_log

    def __str__(self):
        return str(self.error_log)
