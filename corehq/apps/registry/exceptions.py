class RegistryException(Exception):
    pass


class RegistryAccessDenied(RegistryException):
    pass


class RegistryNotFound(RegistryException):
    pass
