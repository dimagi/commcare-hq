from __future__ import absolute_import

import re
from abc import ABCMeta, abstractmethod
from uuid import uuid4

from corehq.blobs import DEFAULT_BUCKET

SAFENAME = re.compile("^[a-z0-9_./-]+$", re.IGNORECASE)


class AbstractBlobDB(object):
    """Storage interface for large binary data objects
    """
    __metaclass__ = ABCMeta

    @abstractmethod
    def put(self, content, basename="", bucket=DEFAULT_BUCKET):
        """Put a blob in persistent storage

        :param content: A file-like object in binary read mode.
        :param basename: Optional name from which the blob name will be
        derived. This is used to make the unique blob name somewhat
        recognizable.
        :param bucket: Optional bucket name used to partition blob data
        in the persistent storage medium. This may be delimited with
        slashes (/). It must be a valid relative path.
        :returns: A `BlobInfo` named tuple. The returned object has a
        `identifier` member that must be used to get or delete the blob. It
        should not be confused with the optional `basename` parameter.
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
    def delete(self, identifier=None, bucket=DEFAULT_BUCKET):
        """Delete a blob

        :param identifier: The identifier of the object to be deleted. The entire
        bucket will be deleted if this is not specified.
        :param bucket: Optional bucket name. This must have the same
        value that was passed to ``put``.
        :returns: True if the blob was deleted else false.
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
    def get_identifier(basename):
        if not basename:
            return uuid4().hex
        if SAFENAME.match(basename) and "/" not in basename:
            prefix = basename
        else:
            prefix = "unsafe"
        return prefix + "." + uuid4().hex
