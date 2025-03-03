class UnsupportedActionException(Exception):
    """Raised when an unknown action is encountered"""


class UnsupportedFilterValueException(Exception):
    """
    Raised when a BulkEditColumnFilter has a value that is unsupported by
    its FilterMatchType and DataType combination. This is rare,
    as the filter creation form should catch most of the issues.
    """
