class DomainLinkError(Exception):
    pass


class DomainLinkAlreadyExists(Exception):
    pass


class DomainLinkNotAllowed(Exception):
    pass


class InvalidPushException(Exception):
    """Raised if attempted push is deemed invalid by validate_push"""
    def __init__(self, message):
        super().__init__()
        self.message = message


class MultipleDownstreamAppsError(Exception):
    pass


class MultipleDownstreamKeywordsError(Exception):
    pass


class RemoteRequestError(Exception):
    def __init__(self, status_code=None):
        self.status_code = status_code


class RemoteAuthError(RemoteRequestError):
    pass


class ActionNotPermitted(RemoteRequestError):
    pass


class UnsupportedActionError(Exception):
    pass


class UserDoesNotHavePermission(Exception):
    pass


class RegistryNotAccessible(Exception):
    pass
