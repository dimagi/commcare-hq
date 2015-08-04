class CouchFormException(Exception):
    """
    A custom exception for the XForms application.
    """
    pass


class XMLSyntaxError(CouchFormException):
    pass


class DuplicateError(CouchFormException):
    pass


class UnexpectedDeletedXForm(Exception):
    pass
