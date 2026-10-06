"""Exceptions raised by HQ web application components."""


class AlreadyRenderedException(Exception):
    pass


class ResourceVersionsNotFoundException(Exception):
    pass


class TemplateTagJSONException(Exception):
    pass


class ChatTokenUnavailable(Exception):
    """OCS could not issue a valid widget credential."""


class ChatUsageUnavailable(Exception):
    """OCS usage could not be obtained or validated."""
