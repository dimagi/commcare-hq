class UnsupportedActionException(Exception):
    """Raised when an unknown action is encountered"""


class UnsupportedFilterValueException(Exception):
    """
    Raised when a BulkEditFilter has a value that is unsupported by
    its FilterMatchType and DataType combination. This is rare,
    as the filter creation form should catch most of the issues.
    """


class SessionAccessClosedException(Exception):
    """
    Raised when a session has been closed for editing. This is
    raised in the view, so that we can redirect to the main page
    with a message.
    """
