
class Error(Exception):
    """BlobDB error"""


class AmbiguousBlobStorageError(Error):
    """Ambiguous blob storage backend error"""


class ArgumentError(Error):
    """Raised on call with wrong arguments"""


class BadName(Error):
    """Blob name error"""


class NotFound(Error):
    """Raised when an attachment cannot be found"""
