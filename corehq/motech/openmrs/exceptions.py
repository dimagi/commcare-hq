from __future__ import unicode_literals


class OpenmrsException(Exception):
    """
    It's not us, it's them
    """
    pass


class OpenmrsConfigurationError(OpenmrsException):
    """
    OpenMRS is configured in a non-standard or unexpected way.
    """
    pass


class OpenmrsFeedDoesNotExist(OpenmrsException):
    pass


class OpenmrsHtmlUiChanged(OpenmrsException):
    """
    OpenMRS HTML UI is no longer what we expect.
    """
    pass
