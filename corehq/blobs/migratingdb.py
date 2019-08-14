"""Filesystem database for large binary data objects (blobs)
"""
from __future__ import absolute_import

from __future__ import unicode_literals
from corehq.blobs.exceptions import NotFound


class MigratingBlobDB(object):
    """Adaptor for migrating from one blob db backend to another"""

    def __init__(self, new_db, old_db):
        self.new_db = new_db
        self.old_db = old_db
        assert new_db.metadb is not old_db.metadb
        self.metadb = new_db.metadb
        # prevent over-reporting of deleted blobs on bulk delete
        # new_db.bulk_delete will delete the metadata
        old_db.metadb.bulk_delete = lambda metas: None

    def put(self, *args, **kw):
        return self.new_db.put(*args, **kw)

    def get(self, *args, **kw):
        try:
            return self.new_db.get(*args, **kw)
        except NotFound:
            return self.old_db.get(*args, **kw)

    def size(self, *args, **kw):
        try:
            return self.new_db.size(*args, **kw)
        except NotFound:
            return self.old_db.size(*args, **kw)

    def exists(self, *args, **kw):
        return self.new_db.exists(*args, **kw) or self.old_db.exists(*args, **kw)

    def delete(self, *args, **kw):
        new_result = self.new_db.delete(*args, **kw)
        old_result = self.old_db.delete(*args, **kw)
        return new_result or old_result

    def bulk_delete(self, *args, **kw):
        new_result = self.new_db.bulk_delete(*args, **kw)
        old_result = self.old_db.bulk_delete(*args, **kw)
        return new_result or old_result

    def expire(self, *args, **kw):
        self.metadb.expire(*args, **kw)

    def copy_blob(self, *args, **kw):
        self.new_db.copy_blob(*args, **kw)
