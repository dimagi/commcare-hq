"""Filesystem database for large binary data objects (blobs)
"""
from __future__ import absolute_import
import base64
import errno
import os
import re
import shutil
import sys
from hashlib import md5
from os.path import commonprefix, exists, isabs, isdir, dirname, join, realpath, sep
from uuid import uuid4

from corehq.blobs import BlobInfo, DEFAULT_BUCKET
from corehq.blobs.exceptions import BadName, NotFound

CHUNK_SIZE = 4096
SAFENAME = re.compile("^[a-z0-9_./-]+$", re.IGNORECASE)


class FilesystemBlobDB(object):
    """Filesystem storage for large binary data objects
    """

    def __init__(self, rootdir):
        assert isabs(rootdir), rootdir
        self.rootdir = rootdir

    def put(self, content, basename="", bucket=DEFAULT_BUCKET):
        """Put a blob in persistent storage

        :param content: A file-like object in binary read mode.
        :param basename: Optional name from which the blob name will be
        derived. This is used to make the unique on-disk filename
        somewhat recognizable.
        :param bucket: Optional bucket name used to partition blob data
        in the persistent storage medium. This may be delimited with
        file path separators. Nested directories will be created for
        each logical path element, so it must be a valid relative path.
        :returns: A `BlobInfo` named tuple. The returned object has a
        `name` member that must be used to get or delete the blob. It
        should not be confused with the optional `basename` parameter.
        """
        name = self.get_unique_name(basename)
        path = self.get_path(name, bucket)
        dirpath = dirname(path)
        if not isdir(dirpath):
            os.makedirs(dirpath)
        length = 0
        digest = md5()
        with openfile(path, "xb") as fh:
            while True:
                chunk = content.read(CHUNK_SIZE)
                if not chunk:
                    break
                fh.write(chunk)
                length += len(chunk)
                digest.update(chunk)
        b64digest = base64.b64encode(digest.digest())
        return BlobInfo(name, length, "md5-" + b64digest)

    def get(self, name, bucket=DEFAULT_BUCKET):
        """Get a blob

        :param name: The name of the object to get.
        :param bucket: Optional bucket name. This must have the same
        value that was passed to ``put``.
        :returns: A file-like object in binary read mode. The returned
        object should be closed when finished reading.
        """
        path = self.get_path(name, bucket)
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
            path = self.get_path(name, bucket)
            remove = os.remove
        if not exists(path):
            return False
        remove(path)
        return True

    def copy_blob(self, content, info, bucket):
        """Copy blob from other blob database

        :param content: File-like blob content object.
        :param info: `BlobInfo` object.
        :param bucket: Bucket name.
        """
        raise NotImplementedError

    @staticmethod
    def get_unique_name(basename):
        if not basename:
            return uuid4().hex
        if SAFENAME.match(basename) and "/" not in basename:
            prefix = basename
        else:
            prefix = "unsafe"
        return prefix + "." + uuid4().hex

    def get_path(self, name=None, bucket=DEFAULT_BUCKET):
        bucket_path = safejoin(self.rootdir, bucket)
        if name is None:
            return bucket_path
        return safejoin(bucket_path, name)


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


def openfile(path, mode="r", *args, **kw):
    """Open file

    Aside from the normal modes accepted by `open()`, this function
    accepts an `x` mode that causes the file to be opened for exclusive-
    write, which means that an exception (`FileExists`) will be raised
    if the file being opened already exists.
    """
    if "x" not in mode or sys.version_info > (3, 0):
        return open(path, mode, *args, **kw)
    # http://stackoverflow.com/a/10979569/10840
    # O_EXCL is only supported on NFS when using NFSv3 or later on kernel 2.6 or later.
    flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY
    try:
        handle = os.open(path, flags)
    except OSError as err:
        if err.errno == errno.EEXIST:
            raise FileExists(path)
        raise
    return os.fdopen(handle, mode.replace("x", "w"), *args, **kw)


try:
    FileExists = FileExistsError
except NameError:
    class FileExists(Exception):
        pass
