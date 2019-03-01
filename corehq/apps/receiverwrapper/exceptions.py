from __future__ import unicode_literals


class LocalSubmissionError(Exception):
    pass


class RepeaterException(Exception):
    pass


class DuplicateFormatException(RepeaterException):
    pass


class IgnoreDocument(RepeaterException):
    """
    This document should be ignored. Do not fire payload.
    """
    pass
