class DomainLinkError(Exception):
    pass


class RemoteRequestError(Exception):
    def __init__(self, status_code=None):
        self.status_code = status_code


class RemoteAuthError(RemoteRequestError):
    pass


class ActionNotPermitted(RemoteRequestError):
    pass
