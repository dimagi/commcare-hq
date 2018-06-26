from __future__ import absolute_import
from __future__ import unicode_literals
from corehq.blobs import DEFAULT_BUCKET
from corehq.blobs.exceptions import InvalidContext


class AtomicBlobs(object):
    """A blob db wrapper that can put and delete blobs atomically

    Usage:

        with AtomicBlobs(get_blob_db()) as db:
            # do stuff here that puts or deletes blobs
            db.delete(old_blob_id)
            meta = db.put(content, ...)
            save(meta, deleted=old_blob_id)

    If an exception occurs inside the `AtomicBlobs` context then all
    blob write operations (puts and deletes) will be rolled back.
    """

    def __init__(self, db):
        self.db = db
        self.puts = None
        self.deletes = None
        self.old_api_puts = None
        self.old_api_deletes = None

    def put(self, content, identifier=None, bucket=DEFAULT_BUCKET, **kw):
        if self.puts is None:
            raise InvalidContext("AtomicBlobs context is not active")
        meta = self.db.put(content, identifier, bucket=bucket, **kw)
        if identifier is None and bucket == DEFAULT_BUCKET:
            self.puts.append(meta)
        else:
            self.old_api_puts.append((meta, bucket))
        return meta

    def get(self, *args, **kw):
        return self.db.get(*args, **kw)

    def delete(self, *args, **kw):
        """Delete a blob

        NOTE blobs will not actually be deleted until the context exits,
        so subsequent gets inside the context will return an object even
        though the blob or bucket has been queued for deletion.
        """
        if self.puts is None:
            raise InvalidContext("AtomicBlobs context is not active")
        if "key" in kw and not args:
            if set(kw) != {"key"}:
                notkey = ", ".join(k for k in kw if k != "key")
                raise TypeError("unexpected arguments: " + notkey)
            self.deletes.append(kw["key"])
        else:
            assert "key" not in kw, kw
            self.old_api_deletes.append((args, kw))
        return None  # result is unknown

    def copy_blob(self, *args, **kw):
        raise NotImplementedError

    def __enter__(self):
        self.puts = []
        self.deletes = []
        self.old_api_puts = []
        self.old_api_deletes = []
        return self

    def __exit__(self, exc_type, exc_value, tb):
        puts, deletes = self.puts, self.deletes
        old_puts, old_deletes = self.old_api_puts, self.old_api_deletes
        self.puts = None
        self.deletes = None
        self.old_api_puts = None
        self.old_api_deletes = None
        if exc_type is None:
            for key in deletes:
                self.db.delete(key=key)
            for args, kw in old_deletes:
                self.db.delete(*args, **kw)
        else:
            if puts:
                self.db.bulk_delete(metas=puts)
            if old_puts:
                for info, bucket in old_puts:
                    self.db.delete(info.identifier, bucket)
