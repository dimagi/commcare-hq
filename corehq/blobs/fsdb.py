"""Filesystem database for large binary data objects (blobs)
"""
from __future__ import absolute_import
import os
import re
import shutil
from hashlib import md5
from os.path import commonprefix, exists, isabs, isdir, dirname, join, realpath, sep

from corehq.blobs.exceptions import BadName, NotFound

CHUNK_SIZE = 4096
DEFAULT_BUCKET = "_default"
SAFENAME = re.compile("^[a-z0-9_./-]+$", re.IGNORECASE)


class FilesystemBlobDB(object):
    """Filesystem storage for large binary data objects
    """

    def __init__(self, rootdir):
        assert isabs(rootdir), rootdir
        self.rootdir = rootdir

    def put(self, content, name, bucket=DEFAULT_BUCKET):
        """Put a blob in persistent storage

        :param content: A file-like object in binary read mode.
        :param name: The name of the object to be saved.
        :param bucket: Optional bucket name used to partition blob data
        in the persistent storage medium. This may be delimited with
        file path separators. Nested directories will be created for
        each logical path element, so it must be a valid relative path.
        Blob names within a single bucket must be unique.
        :returns: Content length (number of bytes persisted).
        """
        path = self._getpath(name, bucket)
        dirpath = dirname(path)
        if not isdir(dirpath):
            os.makedirs(dirpath)
        length = 0
        with open(path, "wb") as fh:
            while True:
                chunk = content.read(CHUNK_SIZE)
                if not chunk:
                    break
                fh.write(chunk)
                length += len(chunk)
        return length

    def get(self, name, bucket=DEFAULT_BUCKET):
        """Get a blob

        :param name: The name of the object to get.
        :param bucket: Optional bucket name. This must have the same
        value that was passed to ``put``.
        :returns: A file-like object in binary read mode. The returned
        object should be closed when finished reading.
        """
        path = self._getpath(name, bucket)
        if not exists(path):
            raise NotFound(name, bucket)
        return open(path, "rb")

    def delete(self, name=None, bucket=DEFAULT_BUCKET):
        """Delete a blob

        :param name: The name of the object to be deleted. The entire
        bucket will be deleted if this is not specified.
        :param bucket: Optional bucket name. This must have the same
        value that was passed to ``put``.
        :returns: True if the blob was deleted else false.
        """
        if name is None:
            path = safejoin(self.rootdir, bucket)
            remove = shutil.rmtree
        else:
            path = self._getpath(name, bucket)
            remove = os.remove
        if not exists(path):
            return False
        remove(path)
        return True

    def _getpath(self, name, bucket):
        bucket_path = safejoin(self.rootdir, bucket)
        prefix = name if SAFENAME.match(name) else "unsafe"
        if isinstance(name, unicode):
            name = name.encode("utf-8")
        hash = md5(name).hexdigest()
        return safejoin(bucket_path, prefix + "." + hash)


def safejoin(root, subpath):
    """Join root to subpath ensuring that the result is actually inside root
    """
    root = realpath(root)
    if not SAFENAME.match(subpath):
        raise BadName(u"unsafe path name: %r" % subpath)
    path = realpath(join(root, subpath))
    if commonprefix([root + sep, path]) != root + sep:
        raise BadName(u"invalid relative path: %r" % subpath)
    return path
