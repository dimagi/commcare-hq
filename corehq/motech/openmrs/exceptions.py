from corehq.motech.exceptions import ConfigurationError


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


class DuplicateCaseMatch(ConfigurationError):
    """
    Multiple CommCare cases match the same OpenMRS patient.

    Either there are two CommCare cases for the same person, or OpenMRS
    repeater configuration needs to be modified to match cases with
    patients more accurately.
    """
    pass
