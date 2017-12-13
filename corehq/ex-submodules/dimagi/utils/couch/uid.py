from __future__ import absolute_import
import uuid

def new():
    """
    Generate a default new uuid
    """
    return uuid.uuid4().hex 