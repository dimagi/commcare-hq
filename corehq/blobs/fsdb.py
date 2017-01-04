"""Filesystem database for large binary data objects (blobs)
"""
from __future__ import absolute_import
import base64
import errno
import os
import shutil
import sys
from hashlib import md5
from os.path import commonprefix, exists, isabs, isdir, dirname, join, realpath, sep

from corehq.blobs import BlobInfo, DEFAULT_BUCKET
from corehq.blobs.exceptions import BadName, NotFound
from corehq.blobs.interface import AbstractBlobDB, SAFENAME

CHUNK_SIZE = 4096


class FilesystemBlobDB(AbstractBlobDB):
    """Filesystem storage for large binary data objects
    """

    def __init__(self, rootdir):
        assert isabs(rootdir), rootdir
        self.rootdir = rootdir

    def put(self, content, identifier, bucket=DEFAULT_BUCKET):
        path = self.get_path(identifier, bucket)
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
        return BlobInfo(identifier, length, "md5-" + b64digest)

    def get(self, identifier, bucket=DEFAULT_BUCKET):
        path = self.get_path(identifier, bucket)
        if not exists(path):
            raise NotFound(identifier, bucket)
        return open(path, "rb")

    def exists(self, identifier, bucket=DEFAULT_BUCKET):
        path = self.get_path(identifier, bucket)
        return exists(path)

    def delete(self, *args, **kw):
        identifier, bucket = self.get_args_for_delete(*args, **kw)
        if identifier is None:
            path = safejoin(self.rootdir, bucket)
            remove = shutil.rmtree
        else:
            path = self.get_path(identifier, bucket)
            remove = os.remove
        if not exists(path):
            return False
        remove(path)
        return True

    def bulk_delete(self, paths):
        success = True
        for path in paths:
            if not exists(path):
                success = False
            else:
                os.remove(path)
        return success

    def copy_blob(self, content, info, bucket):
        raise NotImplementedError

    def get_path(self, identifier=None, bucket=DEFAULT_BUCKET):
        bucket_path = safejoin(self.rootdir, bucket)
        if identifier is None:
            return bucket_path
        return safejoin(bucket_path, identifier)


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
