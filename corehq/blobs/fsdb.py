"""Filesystem database for large binary data objects (blobs)
"""
import os
from collections import namedtuple
from hashlib import md5
from os.path import commonprefix, exists, isabs, isdir, dirname, join, realpath, sep

from corehq.blobs.exceptions import BadName, NotFound
from corehq.blobs.interface import AbstractBlobDB
from corehq.blobs.util import check_safe_key
from corehq.util.datadog.gauges import datadog_counter

CHUNK_SIZE = 4096


class FilesystemBlobDB(AbstractBlobDB):
    """Filesystem storage for large binary data objects
    """

    def __init__(self, rootdir):
        super(FilesystemBlobDB, self).__init__()
        assert isabs(rootdir), rootdir
        self.rootdir = rootdir

    def put(self, content, **blob_meta_args):
        meta = self.metadb.new(**blob_meta_args)
        path = self.get_path(meta.key)
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
        meta.content_length = length
        self.metadb.put(meta)
        return meta

    def get(self, key):
        path = self.get_path(key)
        if not exists(path):
            datadog_counter('commcare.blobdb.notfound')
            raise NotFound(key)
        return open(path, "rb")

    def size(self, key):
        path = self.get_path(key)
        if not exists(path):
            datadog_counter('commcare.blobdb.notfound')
            raise NotFound(key)
        return _count_size(path).size

    def exists(self, key):
        return exists(self.get_path(key))

    def delete(self, key):
        path = self.get_path(key)
        file_exists = exists(path)
        if file_exists:
            count, size = _count_size(path)
            os.remove(path)
        else:
            size = 0
        self.metadb.delete(key, size)
        return file_exists

    def bulk_delete(self, metas):
        success = True
        for meta in metas:
            path = self.get_path(meta.key)
            if not exists(path):
                success = False
            else:
                os.remove(path)
        self.metadb.bulk_delete(metas)
        return success

    def copy_blob(self, content, key):
        path = self.get_path(key)
        dirpath = dirname(path)
        if not isdir(dirpath):
            os.makedirs(dirpath)
        with open(path, "wb") as fh:
            while True:
                chunk = content.read(CHUNK_SIZE)
                if not chunk:
                    break
                fh.write(chunk)

    def get_path(self, key):
        return safejoin(self.rootdir, key)


def safejoin(root, subpath):
    """Join root to subpath ensuring that the result is actually inside root
    """
    check_safe_key(subpath)
    root = realpath(root)
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
