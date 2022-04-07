class DomainLinkError(Exception):
    pass


class DomainLinkAlreadyExists(Exception):
    pass


class DomainLinkNotAllowed(Exception):
    pass


class AttemptedPushViolatesConstraints(Exception):
    pass


class DomainLinkNotFound(Exception):
    pass


class NoDownstreamDomainsProvided(Exception):
    pass


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
