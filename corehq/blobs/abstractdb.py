"""Filesystem database for large binary data objects (blobs)
"""
from __future__ import absolute_import
import base64
import errno
import os
import re
import shutil
import sys
from abc import ABCMeta, abstractmethod
from hashlib import md5
from os.path import commonprefix, exists, isabs, isdir, dirname, join, realpath, sep
from uuid import uuid4

from kombu import abstract

from corehq.blobs import BlobInfo, DEFAULT_BUCKET
from corehq.blobs.exceptions import BadName, NotFound

CHUNK_SIZE = 4096
SAFENAME = re.compile("^[a-z0-9_./-]+$", re.IGNORECASE)


class AbstractBlobDB(object):
    """Filesystem storage for large binary data objects
    """
    __metaclass__ = ABCMeta

    @abstractmethod
    def put(self, content, basename="", bucket=DEFAULT_BUCKET, content_md5=None, unique_id=None):
        """Put a blob in persistent storage

        :param content: A file-like object in binary read mode.
        :param basename: Optional name from which the blob name will be
        derived. This is used to make the unique blob name somewhat
        recognizable.
        :param bucket: Optional bucket name used to partition blob data
        in the persistent storage medium. This may be delimited with
        slashes (/). It must be a valid relative path.
        :param content_md5: RFC-1864-compliant Content-MD5 header value.
        If this parameter is omitted or its value is `None` then content
        must be a seekable file-like object. NOTE: the value should not
        be prefixed with `md5-` even though we store it that way.
        :param unique_id: A globally unique identifier for this blob. If one is not
        provided then one will be generated.
        :returns: A `BlobInfo` named tuple. The returned object has a
        `name` member that must be used to get or delete the blob. It
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
    def get_from_unique_id(self, basename, unique_id, bucket=DEFAULT_BUCKET):
        """Get a blob
        :param basename: The basename that was used when saving the blob using ``put``.
        :param unique_id: The unique identifier of this blob.
        :param bucket: Optional bucket name. This must have the same
        value that was passed to ``put``.
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
    def delete_by_unique_id(self, basename, unique_id, bucket=DEFAULT_BUCKET):
        """Delete a blob

        :param basename: The basename that was used when saving the blob using ``put``.
        :param unique_id: The unique identifier of this blob.
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
    def get_identifier(basename, unique_id):
        if not basename:
            return unique_id
        if SAFENAME.match(basename) and "/" not in basename:
            prefix = basename
        else:
            prefix = "unsafe"
        return prefix + "." + unique_id
