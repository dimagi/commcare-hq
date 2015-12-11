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
