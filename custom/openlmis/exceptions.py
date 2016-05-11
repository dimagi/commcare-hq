

class OpenLMISAPIException(Exception):
    pass


class BadParentException(OpenLMISAPIException):
    """
    When the API references a parent we don't know about.
    """
    pass
