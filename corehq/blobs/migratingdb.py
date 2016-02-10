"""Filesystem database for large binary data objects (blobs)
"""
from __future__ import absolute_import

from corehq.blobs.exceptions import NotFound


class MigratingBlobDB(object):
    """Adaptor for migrating from one blob db backend to another"""

    def __init__(self, new_db, old_db):
        self.new_db = new_db
        self.old_db = old_db

    def put(self, *args, **kw):
        return self.new_db.put(*args, **kw)

    def get(self, *args, **kw):
        try:
            return self.new_db.get(*args, **kw)
        except NotFound:
            return self.old_db.get(*args, **kw)

    def delete(self, *args, **kw):
        new_result = self.new_db.delete(*args, **kw)
        old_result = self.old_db.delete(*args, **kw)
        return new_result or old_result

    def get_path(self, *args, **kw):
        return self.new_db.get_path(*args, **kw)

    def copy_blob(self, content, info, bucket):
        self.new_db.copy_blob(content, info, bucket)
