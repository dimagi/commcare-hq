

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
