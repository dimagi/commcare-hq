
class Error(Exception):
    """BlobDB error"""


class BadName(Error):
    """Blob name error"""


class NotFound(Error):
    """Raised when an attachment cannot be found"""
