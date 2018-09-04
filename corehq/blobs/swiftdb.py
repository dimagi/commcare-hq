from __future__ import absolute_import
from __future__ import unicode_literals

from contextlib import contextmanager

from swiftclient import ClientException, Connection

from corehq.blobs import BlobInfo, DEFAULT_BUCKET
from corehq.blobs.exceptions import NotFound
from corehq.blobs.interface import AbstractBlobDB
from corehq.blobs.s3db import get_file_size, get_content_md5, safejoin, BlobStream
from corehq.blobs.util import (
    check_safe_key,
    set_blob_expire_object,
)
from corehq.util.datadog.gauges import datadog_counter, datadog_bucket_timer
from dimagi.utils.logging import notify_exception

DEFAULT_S3_BUCKET = "blobdb"

CHUNK_SIZE = 2 ** 16


class SwiftBlobDB(AbstractBlobDB):
    """
    https://docs.openstack.org/python-swiftclient/latest/service-api.html#stat
    https://developer.openstack.org/api-ref/object-store/
    https://docs.openstack.org/swift/latest/#object-storage-v1-rest-api-documentation
    """

    def __init__(self, config):
        super(SwiftBlobDB, self).__init__()
        self.container = config.pop('container')
        self.config = config

    def _get_conn(self):
        return Connection(**self.config)

    def report_timing(self, action, key):
        def record_long_request(duration):
            if duration > 100:
                notify_exception(None, "SwiftBlobDB request took a long time.", details={
                    'duration': duration,
                    'action': action,
                    'key': key,
                })

        return datadog_bucket_timer('commcare.blobs.requests.timing', tags=[
            'action:{}'.format(action),
        ], timing_buckets=(.03, .1, .3, 1, 3, 10, 30, 100), callback=record_long_request)

    def put(self, content, identifier=None, bucket=DEFAULT_BUCKET, **blob_meta_args):
        if identifier is None and bucket == DEFAULT_BUCKET:
            meta = self.metadb.new(**blob_meta_args)
            key = meta.key
        else:
            # legacy: can be removed with old API
            assert set(blob_meta_args).issubset({"timeout"}), blob_meta_args
            meta = None
            key = self.get_path(identifier, bucket)
        check_safe_key(key)

        connection = self._get_conn()
        if isinstance(content, BlobStream) and content.blob_db is self:
            stats = connection.head_object(self.container, content.blob_key)
            content_length = int(stats['content-length'])
            if meta is not None:
                meta.content_length = content_length
                self.metadb.put(meta)
            else:
                # legacy: can be removed with old API
                # unfortunately cannot get content-md5 here
                meta = BlobInfo(identifier, content_length, None)

            with self.report_timing('put-via-copy', key):
                connection.copy_object(self.container, content.blob_key, key)
        else:
            content.seek(0)
            if meta is not None:
                meta.content_length = get_file_size(content)
                self.metadb.put(meta)
            else:
                # legacy: can be removed with old API
                timeout = blob_meta_args.get("timeout")
                content_md5 = get_content_md5(content)
                content_length = get_file_size(content)
                if timeout is not None:
                    set_blob_expire_object(bucket, identifier, content_length, timeout)
                datadog_counter('commcare.blobs.added.count')
                datadog_counter('commcare.blobs.added.bytes', value=content_length)
                meta = BlobInfo(identifier, content_length, "md5-" + content_md5)
            with self.report_timing('put', key):
                connection.put_object(self.container, key, content)
        return meta

    def get(self, identifier=None, bucket=DEFAULT_BUCKET, key=None):
        if not (identifier is None and bucket == DEFAULT_BUCKET):
            # legacy: can be removed with old API
            assert key is None, key
            key = self.get_path(identifier, bucket)
        check_safe_key(key)
        with maybe_not_found(throw=NotFound(key)), self.report_timing('get', key):
            headers_, body = self._get_conn().get_object(self.container, key, resp_chunk_size=CHUNK_SIZE)
        return BlobStream(body, self, key)

    def size(self, identifier=None, bucket=DEFAULT_BUCKET, key=None):
        if not (identifier is None and bucket == DEFAULT_BUCKET):
            # legacy: can be removed with old API
            assert key is None, key
            key = self.get_path(identifier, bucket)
        check_safe_key(key)
        with maybe_not_found(throw=NotFound(key)), self.report_timing('size', key):
            stats = self._get_conn().head_object(self.container, key)
            return int(stats['content-length'])

    def exists(self, identifier=None, bucket=DEFAULT_BUCKET, key=None):
        if not (identifier is None and bucket == DEFAULT_BUCKET):
            # legacy: can be removed with old API
            assert key is None, key
            key = self.get_path(identifier, bucket)
        check_safe_key(key)
        try:
            with maybe_not_found(throw=NotFound(key)), self.report_timing('exists', key):
                self._get_conn().head_object(self.container, key)
            return True
        except NotFound:
            return False

    def delete(self, *args, **kw):
        conn = self._get_conn()
        if "key" in kw:
            assert set(kw) == {"key"} and not args, (args, kw)
            key = kw["key"]
            check_safe_key(key)
            success = False
            with maybe_not_found():
                stats = conn.head_object(self.container, key)
                # may raise a not found error -> return False
                deleted_bytes = int(stats['content-length'])
                conn.delete_object(self.container, key)
                success = True
            self.metadb.delete(key, deleted_bytes)
            return success

        # legacy: can be removed with old API
        identifier, bucket = self.get_args_for_delete(*args, **kw)
        key = self.get_path(identifier, bucket)
        check_safe_key(key)
        with maybe_not_found():
            success = True
            if identifier is None:
                _, summaries = conn.get_container(self.container, prefix=key + '/')
                objects = []
                deleted_bytes = 0
                for info in summaries:
                    objects.append(info['name'])
                    deleted_bytes += info['bytes']
                deleted_count = 0
                for obj in objects:
                    conn.delete_object(self.container, obj)
                    deleted_count += 1
                success = len(objects) == deleted_count
            else:
                with maybe_not_found():
                    stats = conn.head_object(self.container, key)
                    deleted_bytes = int(stats['content-length'])
                    conn.delete_object(self.container, key)
                    deleted_count = 1
            datadog_counter('commcare.blobs.deleted.count', value=deleted_count)
            datadog_counter('commcare.blobs.deleted.bytes', value=deleted_bytes)
            return success
        return False

    def bulk_delete(self, paths=None, metas=None):
        conn = self._get_conn()
        deleted = 0
        objs = paths if metas is None else metas
        for meta in objs:
            if paths is None:
                with maybe_not_found():
                    conn.delete_object(self.container, meta.key)
                    deleted += 1
            else:
                deleted_bytes = 0
                with maybe_not_found():
                    deleted_bytes += int(conn.head_object(self.container, meta)['content-length'])
                    conn.delete_object(self.container, meta)
                    deleted += 1

        if paths is None:
            self.metadb.bulk_delete(metas)
        else:
            datadog_counter('commcare.blobs.deleted.count', value=deleted)
            datadog_counter('commcare.blobs.deleted.bytes', value=deleted_bytes)

        return len(objs) == deleted

    def copy_blob(self, content, info=None, bucket=None, key=None):
        if not (info is None and bucket is None):
            # legacy: can be removed with old API
            assert key is None, key
            key = self.get_path(info.identifier, bucket)
        with self.report_timing('copy_blobdb', key):
            self._get_conn().put_object(self.container, key, content)

    def get_path(self, identifier=None, bucket=DEFAULT_BUCKET):
        if identifier is None:
            check_safe_key(bucket)
            return bucket
        return safejoin(bucket, identifier)


@contextmanager
def maybe_not_found(throw=None):
    try:
        yield
    except ClientException as err:
        if not err.http_status == 404:
            datadog_counter('commcare.blobdb.notfound')
            raise
        if throw is not None:
            raise throw
