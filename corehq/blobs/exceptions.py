

class Error(Exception):
    """BlobDB error"""


class AmbiguousBlobStorageError(Error):
    """Ambiguous blob storage backend error"""


class BadName(Error):
    """Blob name error"""


class InvalidContext(Error):
    """Raise when code is executed outside a valid context"""


class NotFound(Error):
    """Raised when an attachment cannot be found"""


class GzipStreamError(Exception):
    """Raised when GzipStream is used improperly"""
