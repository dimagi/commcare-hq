from __future__ import absolute_import
from __future__ import unicode_literals

import os
import weakref
from contextlib import contextmanager
from io import RawIOBase, UnsupportedOperation

from django import settings

from corehq.blobs.exceptions import NotFound
from corehq.blobs.interface import AbstractBlobDB
from corehq.blobs.util import check_safe_key
from corehq.util.datadog.gauges import datadog_counter, datadog_bucket_timer
from dimagi.utils.logging import notify_exception

from dimagi.utils.chunked import chunked

import boto3
from botocore.client import Config
from botocore.exceptions import ClientError
from botocore.utils import fix_s3_host

DEFAULT_S3_BUCKET = "blobdb"
DEFAULT_BULK_DELETE_CHUNKSIZE = 1000


class S3BlobDB(AbstractBlobDB):

    def __init__(self, config):
        super(S3BlobDB, self).__init__()
        kwargs = {}
        if "config" in config:
            kwargs["config"] = Config(**config["config"])
        self.db = boto3.resource(
            's3',
            endpoint_url=config.get("url"),
            aws_access_key_id=config.get("access_key", ""),
            aws_secret_access_key=config.get("secret_key", ""),
            **kwargs
        )
        self.bulk_delete_chunksize = config.get("bulk_delete_chunksize", DEFAULT_BULK_DELETE_CHUNKSIZE)
        self.s3_bucket_name = config.get("s3_bucket", DEFAULT_S3_BUCKET)
        self._s3_bucket_exists = False
        # https://github.com/boto/boto3/issues/259
        self.db.meta.client.meta.events.unregister('before-sign.s3', fix_s3_host)

    def report_timing(self, action, key):
        def record_long_request(duration):
            if duration > 100:
                notify_exception(None, "S3BlobDB request took a long time.", details={
                    'duration': duration,
                    's3_bucket_name': self.s3_bucket_name,
                    'action': action,
                    'key': key,
                })

        return datadog_bucket_timer('commcare.blobs.requests.timing', tags=[
            'action:{}'.format(action),
            's3_bucket_name:{}'.format(self.s3_bucket_name)
        ], timing_buckets=(.03, .1, .3, 1, 3, 10, 30, 100), callback=record_long_request)

    def put(self, content, **blob_meta_args):
        meta = self.metadb.new(**blob_meta_args)
        check_safe_key(meta.key)
        if settings.BUCKET_NAME_FUNCTION:
            s3_bucket_name = settings.BUCKET_NAME_FUNCTION()
            s3_bucket = self._s3_bucket(bucket=s3_bucket_name)  # assumes bucket exists
            meta.bucket = s3_bucket_name
        else:
            s3_bucket_name = self.s3_bucket_name
            s3_bucket = self._s3_bucket(create=True)

        if isinstance(content, BlobStream) and content.blob_db is self:
            obj = s3_bucket.Object(content.blob_key)
            meta.content_length = obj.content_length
            self.metadb.put(meta)
            source = {"Bucket": s3_bucket_name, "Key": content.blob_key}
            with self.report_timing('put-via-copy', meta.key):
                s3_bucket.copy(source, meta.key)
        else:
            content.seek(0)
            meta.content_length = get_file_size(content)
            self.metadb.put(meta)
            with self.report_timing('put', meta.key):
                s3_bucket.upload_fileobj(content, meta.key)
        return meta

    def get(self, key, bucket=None):
        check_safe_key(key)
        with maybe_not_found(throw=NotFound(key)), self.report_timing('get', key):
            resp = self._s3_bucket(bucket=bucket).Object(key).get()
        return BlobStream(resp["Body"], self, key)

    def size(self, key):
        check_safe_key(key)
        with maybe_not_found(throw=NotFound(key)), self.report_timing('size', key):
            return self._s3_bucket().Object(key).content_length

    def exists(self, key):
        check_safe_key(key)
        try:
            with maybe_not_found(throw=NotFound(key)), self.report_timing('exists', key):
                self._s3_bucket().Object(key).load()
            return True
        except NotFound:
            return False

    def delete(self, key):
        deleted_bytes = 0
        check_safe_key(key)
        success = False
        with maybe_not_found(), self.report_timing('delete', key):
            success = True
            obj = self._s3_bucket().Object(key)
            # may raise a not found error -> return False
            deleted_bytes = obj.content_length
            obj.delete()
            success = True
        self.metadb.delete(key, deleted_bytes)
        return success

    def bulk_delete(self, metas):
        success = True
        s3_bucket = self._s3_bucket()
        for chunk in chunked(metas, self.bulk_delete_chunksize):
            objects = [{"Key": meta.key} for meta in chunk]
            resp = s3_bucket.delete_objects(Delete={"Objects": objects})
            deleted = set(d["Key"] for d in resp.get("Deleted", []))
            success = success and all(o["Key"] in deleted for o in objects)
            self.metadb.bulk_delete(chunk)
        return success

    def copy_blob(self, content, key):
        with self.report_timing('copy_blobdb', key):
            self._s3_bucket(create=True).upload_fileobj(content, key)

    def _s3_bucket(self, create=False, bucket=None):
        if create and not self._s3_bucket_exists and bucket is None:
            try:
                with self.report_timing('head_bucket', self.s3_bucket_name):
                    self.db.meta.client.head_bucket(Bucket=self.s3_bucket_name)
            except ClientError as err:
                if not is_not_found(err):
                    datadog_counter('commcare.blobdb.notfound')
                    raise
                with self.report_timing('create_bucket', self.s3_bucket_name):
                    self.db.create_bucket(Bucket=self.s3_bucket_name)
            self._s3_bucket_exists = True
        return self.db.Bucket(bucket or self.s3_bucket_name)


class BlobStream(RawIOBase):

    def __init__(self, stream, blob_db, blob_key):
        self._obj = stream
        self._blob_db = weakref.ref(blob_db)
        self.blob_key = blob_key

    def readable(self):
        return True

    def read(self, *args, **kw):
        return self._obj.read(*args, **kw)

    read1 = read

    def write(self, *args, **kw):
        raise IOError

    def tell(self):
        return self._obj._amount_read

    def seek(self, offset, from_what=os.SEEK_SET):
        if from_what != os.SEEK_SET:
            raise ValueError("seek mode not supported")
        pos = self.tell()
        if offset != pos:
            raise ValueError("seek not supported")
        return pos

    def close(self):
        self._obj.close()
        return super(BlobStream, self).close()

    def __getattr__(self, name):
        return getattr(self._obj, name)

    @property
    def blob_db(self):
        return self._blob_db()


def is_not_found(err, not_found_codes=["NoSuchKey", "NoSuchBucket", "404"]):
    return (err.response["Error"]["Code"] in not_found_codes or
        err.response.get("Errors", {}).get("Error", {}).get("Code") in not_found_codes)


def get_file_size(fileobj):
    # botocore.response.StreamingBody has a '_content_length' attribute
    length = getattr(fileobj, "_content_length", None)
    if length is not None:
        return int(length)

    def tell_end(fileobj_):
        pos = fileobj_.tell()
        try:
            fileobj_.seek(0, os.SEEK_END)
            return fileobj_.tell()
        finally:
            fileobj_.seek(pos)

    if not hasattr(fileobj, 'fileno'):
        return tell_end(fileobj)
    try:
        fileno = fileobj.fileno()
    except UnsupportedOperation:
        return tell_end(fileobj)
    return os.fstat(fileno).st_size


@contextmanager
def maybe_not_found(throw=None):
    try:
        yield
    except ClientError as err:
        if not is_not_found(err):
            raise
        datadog_counter('commcare.blobdb.notfound')
        if throw is not None:
            raise throw
