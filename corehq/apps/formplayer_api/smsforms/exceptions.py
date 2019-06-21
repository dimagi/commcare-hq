
from __future__ import unicode_literals


class TouchFormsError(Exception):
    pass


class XFormException(TouchFormsError):
    """
    A custom exception for the XForms application.
    """
    pass


class BadDataError(TouchFormsError):
    pass
