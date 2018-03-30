from __future__ import absolute_import
from __future__ import unicode_literals
from datetime import datetime


def utcnow():
    """
    Defined here to do patching in tests.
    """
    return datetime.utcnow()
