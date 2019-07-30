from __future__ import absolute_import
from __future__ import unicode_literals
from abc import ABCMeta, abstractmethod

from .metadata import MetaDB
import six

NOT_SET = object()


class AbstractBlobDB(six.with_metaclass(ABCMeta, object)):
    """Storage interface for large binary data objects

    The constructor of this class creates a `MetaDB` instance for managing
    blob metadata, so it is important that subclass constructors call it.
    """

    def __init__(self):
        self.metadb = MetaDB()

    @abstractmethod
    def put(self, content, **blob_meta_args):
        """Put a blob in persistent storage

        :param content: A file-like object in binary read mode.
        :param **blob_meta_args: A single `"meta"` argument (`BlobMeta`
        object) or arguments used to construct a `BlobMeta` object:

        - domain - (required, text) domain name.
        - parent_id - (required, text) parent identifier, used for
        sharding.
        - type_code - (required, int) blob type code. See
        `corehq.blobs.CODES`.
        - key - (optional, text) globally unique blob identifier. A
        new key will be generated with `uuid4().hex` if missing or
        `None`. This is the key used to store the blob in the external
        blob store.
        - name - (optional, text) blob name.
        - content_length - (optional, int) content length. Will be
        calculated from the given content if not given.
        - content_type - (optional, text) content type.
        - timeout - minimum number of minutes the object will live in
        the blobdb. `None` means forever. There are no guarantees on the
        maximum time it may live in blob storage.

        NOTE: it is important to delete any blobs saved with this method
        if it is called within a database transaction that ends up being
        rolled back. Otherwise those blobs will be orphaned, meaning
        they will be stored in the blob db backend indefinitely, but
        their metadata will be lost.

        :returns: A `BlobMeta` object. The returned object has a
        `key` attribute that may be used to get or delete the blob.
        """
        raise NotImplementedError

    @abstractmethod
    def get(self, key):
        """Get a blob

        :param key: Blob key.
        :returns: A file-like object in binary read mode. The returned
        object should be closed when finished reading.
        """
        raise NotImplementedError

    @abstractmethod
    def exists(self, key):
        """Check if blob exists

        :param key: Blob key.
        :returns: True if the object exists else false.
        """
        raise NotImplementedError

    @abstractmethod
    def size(self, key):
        """Gets the size of a blob in bytes

        :param key: Blob key.
        :returns: The number of bytes of a blob
        """
        raise NotImplementedError

    @abstractmethod
    def delete(self, key):
        """Delete a blob

        :param key: Blob key.
        :returns: True if the blob was deleted else false. None if it is
        not known if the blob was deleted or not.
        """
        raise NotImplementedError

    @abstractmethod
    def bulk_delete(self, metas):
        """Delete multiple blobs.

        :param metas: The list of `BlobMeta` objects for blobs to delete.
        :returns: True if all the blobs were deleted else false. `None` if
        it is not known if the blob was deleted or not.
        """
        raise NotImplementedError

    def expire(self, *args, **kw):
        """Set blob expiration

        See `metadata.MetaDB.expire` for more details
        """
        self.metadb.expire(*args, **kw)

    @abstractmethod
    def copy_blob(self, content, key):
        """Copy blob from other blob database

        :param content: File-like blob content object.
        :param key: Blob key.
        """
        raise NotImplementedError
