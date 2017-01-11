from corehq.blobs import DEFAULT_BUCKET
from corehq.blobs.exceptions import InvalidContext


class AtomicBlobs(object):
    """A blob db wrapper that can put and delete blobs atomically

    Usage:

        with AtomicBlobs(get_blob_db()) as db:
            # do stuff here that puts or deletes blobs
            db.delete(old_blob_id)
            info = db.put(content, new_blob_id)
            save(info, deleted=old_blob_id)

    If an exception occurs inside the `AtomicBlobs` context then all
    blob write operations (puts and deletes) will be rolled back.
    """

    def __init__(self, db):
        self.db = db
        self.puts = None
        self.deletes = None

    def put(self, content, identifier, bucket=DEFAULT_BUCKET):
        if self.puts is None:
            raise InvalidContext("AtomicBlobs context is not active")
        info = self.db.put(content, identifier, bucket=bucket)
        self.puts.append((info, bucket))
        return info

    def get(self, *args, **kw):
        return self.db.get(*args, **kw)

    def delete(self, *args, **kw):
        """Delete a blob or bucket of blobs

        NOTE blobs will not actually be deleted until the context exits,
        so subsequent gets inside the context will return an object even
        though the blob or bucket has been queued for deletion.
        """
        if self.puts is None:
            raise InvalidContext("AtomicBlobs context is not active")
        self.db.get_args_for_delete(*args, **kw)  # validate args
        self.deletes.append((args, kw))
        return None  # result is unknown

    def copy_blob(self, *args, **kw):
        raise NotImplementedError

    def __enter__(self):
        self.puts = []
        self.deletes = []
        return self

    def __exit__(self, exc_type, exc_value, tb):
        puts, deletes = self.puts, self.deletes
        self.puts = None
        self.deletes = None
        if exc_type is None:
            for args, kw in deletes:
                self.db.delete(*args, **kw)
        else:
            for info, bucket in puts:
                self.db.delete(info.identifier, bucket)
