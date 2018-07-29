from __future__ import absolute_import
from __future__ import unicode_literals
import uuid

def new():
    """
    Generate a default new uuid
    """
    return uuid.uuid4().hex 