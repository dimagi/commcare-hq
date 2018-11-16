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
from corehq.blobs.interface import AbstractBlobDB
from corehq.blobs.util import check_safe_key, set_blob_expire_object
from corehq.util.datadog.gauges import datadog_counter
from io import open

CHUNK_SIZE = 4096


class FilesystemBlobDB(AbstractBlobDB):
    """Filesystem storage for large binary data objects
    """

    def __init__(self, rootdir):
        super(FilesystemBlobDB, self).__init__()
        assert isabs(rootdir), rootdir
        self.rootdir = rootdir

    def put(self, content, identifier=None, bucket=DEFAULT_BUCKET, **blob_meta_args):
        if identifier is None and bucket == DEFAULT_BUCKET:
            meta = self.metadb.new(**blob_meta_args)
            path = self.get_path(key=meta.key)
        else:
            # legacy: can be removed with old API
            assert set(blob_meta_args).issubset({"timeout"}), blob_meta_args
            meta = None
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

        if meta is None:
            # legacy: can be removed with old API
            b64digest = base64.b64encode(digest.digest())
            timeout = blob_meta_args.get("timeout")
            if timeout is not None:
                set_blob_expire_object(bucket, identifier, length, timeout)
            datadog_counter('commcare.blobs.added.count')
            datadog_counter('commcare.blobs.added.bytes', value=length)
            return BlobInfo(identifier, length, "md5-" + b64digest.decode('utf-8'))

        meta.content_length = length
        self.metadb.put(meta)
        return meta

    def get(self, identifier=None, bucket=DEFAULT_BUCKET, key=None):
        if identifier is None and bucket == DEFAULT_BUCKET:
            path = self.get_path(key=key)
        else:
            # legacy: can be removed with old API
            assert key is None, key
            key = join(bucket, identifier)
            path = self.get_path(identifier, bucket)
        if not exists(path):
            datadog_counter('commcare.blobdb.notfound')
            raise NotFound(key)
        return open(path, "rb")

    def size(self, identifier=None, bucket=DEFAULT_BUCKET, key=None):
        if identifier is None and bucket == DEFAULT_BUCKET:
            path = self.get_path(key=key)
        else:
            assert key is None, key
            key = join(bucket, identifier)
            path = self.get_path(identifier, bucket)
        if not exists(path):
            datadog_counter('commcare.blobdb.notfound')
            raise NotFound(key)
        return _count_size(path).size

    def exists(self, identifier=None, bucket=DEFAULT_BUCKET, key=None):
        if identifier is None and bucket == DEFAULT_BUCKET:
            path = self.get_path(key=key)
        else:
            assert key is None, key
            path = self.get_path(identifier, bucket)
        return exists(path)

    def delete(self, *args, **kw):
        if "key" in kw:
            assert set(kw) == {"key"} and not args, (args, kw)
            key = kw["key"]
            path = self.get_path(key=key)
            remove = os.remove
        else:
            # legacy: can be removed with old API
            key = None
            identifier, bucket = self.get_args_for_delete(*args, **kw)
            if identifier is None:
                path = safejoin(self.rootdir, bucket)
                remove = shutil.rmtree
            else:
                path = self.get_path(identifier, bucket)
                remove = os.remove
        file_exists = exists(path)
        if file_exists:
            count, size = _count_size(path)
            remove(path)
            if key is None:
                # legacy: can be removed with old API
                datadog_counter('commcare.blobs.deleted.count', value=count)
                datadog_counter('commcare.blobs.deleted.bytes', value=size)
        else:
            size = 0
        if key is not None:
            self.metadb.delete(key, size)
        return file_exists

    def bulk_delete(self, paths=None, metas=None):
        success = True
        if paths is None:
            for meta in metas:
                path = self.get_path(key=meta.key)
                if not exists(path):
                    success = False
                else:
                    os.remove(path)
            self.metadb.bulk_delete(metas)
        else:
            assert metas is None, metas
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

    def copy_blob(self, content, info=None, bucket=None, key=None):
        if info is None and bucket is None:
            path = self.get_path(key=key)
        else:
            assert key is None, key
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

    def get_path(self, identifier=None, bucket=DEFAULT_BUCKET, key=None):
        if identifier is None and bucket == DEFAULT_BUCKET:
            return safejoin(self.rootdir, key)
        assert key is None, key
        bucket_path = safejoin(self.rootdir, bucket)
        if identifier is None:
            return bucket_path
        return safejoin(bucket_path, identifier)


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
