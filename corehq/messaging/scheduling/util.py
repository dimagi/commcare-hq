from datetime import datetime


def utcnow():
    """
    Defined here to do patching in tests.
    """
    return datetime.utcnow()
