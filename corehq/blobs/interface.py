from __future__ import absolute_import

import re
from abc import ABCMeta, abstractmethod

from corehq.blobs import DEFAULT_BUCKET
from corehq.blobs.exceptions import ArgumentError

SAFENAME = re.compile("^[a-z0-9_./{}-]+$", re.IGNORECASE)
NOT_SET = object()


class AbstractBlobDB(object):
    """Storage interface for large binary data objects
    """
    __metaclass__ = ABCMeta

    @abstractmethod
    def put(self, content, identifier, bucket=DEFAULT_BUCKET):
        """Put a blob in persistent storage

        :param content: A file-like object in binary read mode.
        :param identifier: The blob identifier. This is combined with
        `bucket` to construct a unique key for the blob. It's recommended
        to use `identifier=util.random_url_id(16)` to get a new 128-bit
        key if you don't already have unique identifier for the blob (in
        the bucket).
        :param bucket: Optional bucket name used to partition blob data
        in the persistent storage medium. This may be delimited with
        slashes (/). It must be a valid relative path.
        :returns: A `BlobInfo` named tuple. The returned object has a
        `identifier` member that must be used to get or delete the blob.
        """
        raise NotImplementedError

    @abstractmethod
    def get(self, identifier, bucket=DEFAULT_BUCKET):
        """Get a blob

        :param identifier: The identifier of the object to get.
        :param bucket: Optional bucket name. This must have the same
        value that was passed to ``put``.
        :returns: A file-like object in binary read mode. The returned
        object should be closed when finished reading.
        """
        raise NotImplementedError

    @abstractmethod
    def exists(self, identifier, bucket=DEFAULT_BUCKET):
        """Check if blob exists

        :param identifier: The identifier of the object to get.
        :param bucket: Optional bucket name. This must have the same
        value that was passed to ``put``.
        :returns: True if the object exists else false.
        """
        raise NotImplementedError

    @abstractmethod
    def delete(self, identifier=NOT_SET, bucket=NOT_SET):
        """Delete a blob or bucket of blobs

        Either one or both of `identifier` or `bucket` parameters
        is required.

        :param identifier: The identifier of the object to be deleted.
        The entire bucket will be deleted if this is not provided.
        :param bucket: Bucket name. This must have the same value that
        was passed to ``put``. Delete will be attempted in the default
        bucket if an identifier is given but the bucket is not given.
        Pass this parameter alone as a keyword argument to delete the
        entire bucket.
        :returns: True if the blob was deleted else false. None if it is
        not known if the blob was deleted or not.
        """
        raise NotImplementedError

    @abstractmethod
    def bulk_delete(self, paths):
        """Delete multiple blobs.

        :param paths: The list of blob paths to delete.
        :returns: True if all the blobs were deleted else false. None if it is
        not known if the blob was deleted or not.
        """
        raise NotImplementedError

    @abstractmethod
    def copy_blob(self, content, info, bucket):
        """Copy blob from other blob database

        :param content: File-like blob content object.
        :param info: `BlobInfo` object.
        :param bucket: Bucket name.
        """
        raise NotImplementedError

    @staticmethod
    def get_args_for_delete(identifier=NOT_SET, bucket=NOT_SET):
        if identifier is NOT_SET and bucket is NOT_SET:
            raise ArgumentError("'identifier' and/or 'bucket' is required")
        if identifier is None:
            raise ArgumentError("refusing to delete entire bucket when "
                                "null blob identifier is provided (either "
                                "provide a real blob identifier or pass "
                                "bucket as keyword argument)")
        if identifier is NOT_SET:
            assert bucket is not NOT_SET
            identifier = None
        elif bucket is NOT_SET:
            bucket = DEFAULT_BUCKET
        return identifier, bucket
