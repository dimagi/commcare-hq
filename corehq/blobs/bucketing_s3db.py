from __future__ import absolute_import
from __future__ import unicode_literals

import hashlib
import itertools

import boto3
from botocore.client import Config
from botocore.exceptions import ClientError
from botocore.utils import fix_s3_host

from dimagi.utils.chunked import chunked
from dimagi.utils.logging import notify_exception

from corehq.blobs.exceptions import NotFound
from corehq.blobs.interface import AbstractBlobDB
from corehq.blobs.models import KeyBucketMapping
from corehq.blobs.s3db import BlobStream, get_file_size, is_not_found, maybe_not_found
from corehq.blobs.util import check_safe_key
from corehq.sql_db.util import get_db_aliases_for_partitioned_query
from corehq.util.datadog.gauges import datadog_bucket_timer, datadog_counter

DEFAULT_S3_BUCKET = "blobdb"
DEFAULT_BULK_DELETE_CHUNKSIZE = 1000


class BucketHashingS3BlobDB(AbstractBlobDB):

    def __init__(self, config):
        super(BucketHashingS3BlobDB, self).__init__()
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
        # could be simplified by storing self._default_bucket_name and changin dict to {bucket_name: created}
        self.buckets = {
            '__default__': [config.get("s3_bucket", DEFAULT_S3_BUCKET), False]
        }
        # https://github.com/boto/boto3/issues/259
        self.db.meta.client.meta.events.unregister('before-sign.s3', fix_s3_host)

    def report_timing(self, action, key):
        bucket = self._get_bucket(key)

        def record_long_request(duration):
            if duration > 100:
                notify_exception(None, "S3BlobDB request took a long time.", details={
                    'duration': duration,
                    's3_bucket_name': bucket,
                    'action': action,
                    'key': key,
                })

        return datadog_bucket_timer('commcare.blobs.requests.timing', tags=[
            'action:{}'.format(action),
            's3_bucket_name:{}'.format(bucket)
        ], timing_buckets=(.03, .1, .3, 1, 3, 10, 30, 100), callback=record_long_request)

    def put(self, content, **blob_meta_args):
        meta = self.metadb.new(**blob_meta_args)
        check_safe_key(meta.key)
        s3_bucket = self._s3_bucket(meta.key, create=True)
        if isinstance(content, BlobStream) and content.blob_db is self:
            obj = s3_bucket.Object(content.blob_key)
            meta.content_length = obj.content_length
            self.metadb.put(meta)
            source = {"Bucket": self.s3_bucket_name, "Key": content.blob_key}
            with self.report_timing('put-via-copy', meta.key):
                s3_bucket.copy(source, meta.key)
        else:
            content.seek(0)
            meta.content_length = get_file_size(content)
            self.metadb.put(meta)
            with self.report_timing('put', meta.key):
                s3_bucket.upload_fileobj(content, meta.key)
        # this should be before the put, or it should use update_or_create, or update but log conflicts
        KeyBucketMapping.objects.create(key=meta.key, bucket=s3_bucket.name)
        return meta

    def get(self, key):
        check_safe_key(key)
        with maybe_not_found(throw=NotFound(key)), self.report_timing('get', key):
            resp = self._s3_bucket(key).Object(key).get()
        return BlobStream(resp["Body"], self, key)

    def size(self, key):
        check_safe_key(key)
        with maybe_not_found(throw=NotFound(key)), self.report_timing('size', key):
            return self._s3_bucket(key).Object(key).content_length

    def exists(self, key):
        check_safe_key(key)
        try:
            with maybe_not_found(throw=NotFound(key)), self.report_timing('exists', key):
                self._s3_bucket(key).Object(key).load()
            return True
        except NotFound:
            return False

    def delete(self, key):
        deleted_bytes = 0
        check_safe_key(key)
        success = False
        with maybe_not_found(), self.report_timing('delete', key):
            obj = self._s3_bucket(key).Object(key)
            # may raise a not found error -> return False
            deleted_bytes = obj.content_length
            obj.delete()
            success = True
        self.metadb.delete(key, deleted_bytes)
        return success

    def bulk_delete(self, metas):
        # TODO Figure out good way for this
        success = True
        for chunk in chunked(metas, self.bulk_delete_chunksize):
            sorted_chunk = sorted(chunk, lambda meta: self._get_bucket(meta.key))
            for bucket, metas in itertools.groupby(sorted_chunk, lambda meta: self._get_bucket(meta.key)):
                s3_bucket = self.db.Bucket(bucket)
                objects = [{"Key": meta.key} for meta in metas]
                resp = s3_bucket.delete_objects(Delete={"Objects": objects})
                deleted = set(d["Key"] for d in resp.get("Deleted", []))
                success = success and all(o["Key"] in deleted for o in objects)
                self.metadb.bulk_delete(metas)
        return success

    def copy_blob(self, content, key):
        with self.report_timing('copy_blobdb', key):
            self._s3_bucket(key, create=True).upload_fileobj(content, key)

    def _s3_bucket(self, key, create=False):
        if create is True:
            bucket_name = self._generate_bucket_name(key)
        else:
            bucket_name = self._get_bucket(key)

        if bucket_name not in self.buckets:
            self.buckets[bucket_name] = [bucket_name, False]

        if create and not self.buckets[bucket_name][1]:
            try:
                with self.report_timing('head_bucket', bucket_name):
                    self.db.meta.client.head_bucket(Bucket=bucket_name)
            except ClientError as err:
                if not is_not_found(err):
                    datadog_counter('commcare.blobdb.notfound')
                    raise
                with self.report_timing('create_bucket', bucket_name):
                    self.db.create_bucket(Bucket=bucket_name)
            self.buckets[self._s3_bucket_exists][1] = True

        return self.db.Bucket(bucket_name)

    def _generate_bucket_name(self, key):
        return hashlib.md5(key.encode())[:3]

    def _get_bucket(self, key):
        db_alias = get_db_aliases_for_partitioned_query(key)
        key_bucket = KeyBucketMapping.objects.using(db_alias).filter(key=key).first()
        if key_bucket:
            return key_bucket.bucket
        return "__default__"
