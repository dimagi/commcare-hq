"""Filesystem database for large binary data objects (blobs)
"""
from __future__ import absolute_import
from __future__ import unicode_literals
import base64
import os
import shutil
from collections import namedtuple
from hashlib import md5
from os.path import commonprefix, exists, isabs, isdir, dirname, join, realpath, sep

from corehq.blobs import BlobInfo, DEFAULT_BUCKET
from corehq.blobs.exceptions import BadName, NotFound
from corehq.blobs.interface import AbstractBlobDB, SAFENAME
from corehq.blobs.util import set_blob_expire_object
from corehq.util.datadog.gauges import datadog_counter
from io import open

CHUNK_SIZE = 4096


class FilesystemBlobDB(AbstractBlobDB):
    """Filesystem storage for large binary data objects
    """

    def __init__(self, rootdir):
        assert isabs(rootdir), rootdir
        self.rootdir = rootdir

    def put(self, content, identifier, bucket=DEFAULT_BUCKET, timeout=None):
        path = self.get_path(identifier, bucket)
        dirpath = dirname(path)
        if not isdir(dirpath):
            os.makedirs(dirpath)
        length = 0
        digest = md5()
        with open(path, "wb") as fh:
            while True:
                chunk = content.read(CHUNK_SIZE)
                if not chunk:
                    break
                fh.write(chunk)
                length += len(chunk)
                digest.update(chunk)
        b64digest = base64.b64encode(digest.digest())
        if timeout is not None:
            set_blob_expire_object(bucket, identifier, length, timeout)
        datadog_counter('commcare.blobs.added.count')
        datadog_counter('commcare.blobs.added.bytes', value=length)
        return BlobInfo(identifier, length, "md5-" + b64digest)

    def get(self, identifier, bucket=DEFAULT_BUCKET):
        path = self.get_path(identifier, bucket)
        if not exists(path):
            datadog_counter('commcare.blobdb.notfound')
            raise NotFound(identifier, bucket)
        return open(path, "rb")

    def size(self, identifier, bucket=DEFAULT_BUCKET):
        path = self.get_path(identifier, bucket)
        if not exists(path):
            datadog_counter('commcare.blobdb.notfound')
            raise NotFound(identifier, bucket)
        return _count_size(path).size

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
        cs = _count_size(path)
        datadog_counter('commcare.blobs.deleted.count', value=cs.count)
        datadog_counter('commcare.blobs.deleted.bytes', value=cs.size)
        remove(path)
        return True

    def bulk_delete(self, paths):
        success = True
        deleted_count = 0
        deleted_bytes = 0
        for path in paths:
            if not exists(path):
                success = False
            else:
                cs = _count_size(path)
                deleted_count += cs.count
                deleted_bytes += cs.size
                os.remove(path)
        datadog_counter('commcare.blobs.deleted.count', value=deleted_count)
        datadog_counter('commcare.blobs.deleted.bytes', value=deleted_bytes)
        return success

    def copy_blob(self, content, info, bucket):
        path = self.get_path(info.identifier, bucket)
        dirpath = dirname(path)
        if not isdir(dirpath):
            os.makedirs(dirpath)
        with open(path, "wb") as fh:
            while True:
                chunk = content.read(CHUNK_SIZE)
                if not chunk:
                    break
                fh.write(chunk)

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
        raise BadName("unsafe path name: %r" % subpath)
    path = realpath(join(root, subpath))
    if commonprefix([root + sep, path]) != root + sep:
        raise BadName("invalid relative path: %r" % subpath)
    return path


def _count_size(path):
    if isdir(path):
        count = 0
        size = 0
        for root, dirs, files in os.walk(path):
            count += len(files)
            size += sum(os.path.getsize(join(root, name)) for name in files)
    else:
        count = 1
        size = os.path.getsize(path)
    return _CountSize(count, size)


_CountSize = namedtuple("_CountSize", "count size")
