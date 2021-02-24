from contextlib import contextmanager
from gzip import GzipFile

import boto3
from botocore.client import Config
from botocore.exceptions import ClientError
from botocore.utils import fix_s3_host

from dimagi.utils.chunked import chunked
from dimagi.utils.logging import notify_exception

from corehq.blobs.exceptions import NotFound
from corehq.blobs.interface import AbstractBlobDB
from corehq.blobs.retry_s3db import retry_on_slow_down
from corehq.blobs.util import (
    BlobStream,
    GzipStream,
    check_safe_key,
    get_content_size,
)
from corehq.util.metrics import metrics_counter, metrics_histogram_timer

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

        return metrics_histogram_timer(
            'commcare.blobs.requests.timing',
            timing_buckets=(.03, .1, .3, 1, 3, 10, 30, 100),
            tags={
                'action': action,
                's3_bucket_name': self.s3_bucket_name
            },
            callback=record_long_request
        )

    def put(self, content, **blob_meta_args):
        meta = self.metadb.new(**blob_meta_args)
        check_safe_key(meta.key)
        s3_bucket = self._s3_bucket(create=True)
        if isinstance(content, BlobStream) and content.blob_db is self:
            meta.content_length = content.content_length
            meta.compressed_length = content.compressed_length
            self.metadb.put(meta)
            source = {"Bucket": self.s3_bucket_name, "Key": content.blob_key}
            with self.report_timing('put-via-copy', meta.key):
                s3_bucket.copy(source, meta.key)
        else:
            content.seek(0)
            if meta.is_compressed:
                content = GzipStream(content)

            chunk_sizes = []

            def _track_transfer(bytes_sent):
                chunk_sizes.append(bytes_sent)

            with self.report_timing('put', meta.key):
                s3_bucket.upload_fileobj(content, meta.key, Callback=_track_transfer)
            meta.content_length, meta.compressed_length = get_content_size(content, chunk_sizes)
            self.metadb.put(meta)
        return meta

    @retry_on_slow_down
    def get(self, key=None, type_code=None, meta=None):
        key = self._validate_get_args(key, type_code, meta)
        check_safe_key(key)
        with maybe_not_found(throw=NotFound(key)), self.report_timing('get', key):
            resp = self._s3_bucket().Object(key).get()
        reported_content_length = resp['ContentLength']

        body = resp["Body"]
        if meta and meta.is_compressed:
            content_length, compressed_length = meta.content_length, meta.compressed_length
            body = GzipFile(key, mode='rb', fileobj=body)
        else:
            content_length, compressed_length = reported_content_length, None
        return BlobStream(body, self, key, content_length, compressed_length)

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

    def _s3_bucket(self, create=False):
        if create and not self._s3_bucket_exists:
            try:
                with self.report_timing('head_bucket', self.s3_bucket_name):
                    self.db.meta.client.head_bucket(Bucket=self.s3_bucket_name)
            except ClientError as err:
                if not is_not_found(err):
                    metrics_counter('commcare.blobdb.notfound')
                    raise
                with self.report_timing('create_bucket', self.s3_bucket_name):
                    self.db.create_bucket(Bucket=self.s3_bucket_name)
            self._s3_bucket_exists = True
        return self.db.Bucket(self.s3_bucket_name)


def is_not_found(err, not_found_codes=["NoSuchKey", "NoSuchBucket", "404"]):
    return (err.response["Error"]["Code"] in not_found_codes or
        err.response.get("Errors", {}).get("Error", {}).get("Code") in not_found_codes)


@contextmanager
def maybe_not_found(throw=None):
    try:
        yield
    except ClientError as err:
        if not is_not_found(err):
            raise
        metrics_counter('commcare.blobdb.notfound')
        if throw is not None:
            raise throw
