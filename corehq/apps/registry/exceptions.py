class RegistryException(Exception):
    pass


class RegistryAccessDenied(RegistryException):
    """This exception is raised when a domain attempts to access a registry it does not have access to."""
    pass


class RegistryNotFound(RegistryException):
    """No registry exists"""
    pass


class RegistryAccessException(RegistryException):
    """This exception is raise for data access errors when a domain is requesting data from
    a registry that the domain does have access to"""
    pass
