from __future__ import absolute_import
from __future__ import unicode_literals
import os
import weakref
from contextlib import contextmanager
from io import UnsupportedOperation

from corehq.blobs import BlobInfo, DEFAULT_BUCKET
from corehq.blobs.exceptions import BadName, NotFound
from corehq.blobs.interface import AbstractBlobDB, SAFENAME
from corehq.blobs.util import ClosingContextProxy, set_blob_expire_object
from corehq.util.datadog.gauges import datadog_counter, datadog_bucket_timer
from dimagi.utils.logging import notify_exception

from dimagi.utils.chunked import chunked

import boto3
from botocore.client import Config
from botocore.handlers import calculate_md5
from botocore.exceptions import ClientError
from botocore.utils import fix_s3_host

DEFAULT_S3_BUCKET = "blobdb"


class S3BlobDB(AbstractBlobDB):

    def __init__(self, config):
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
        self.s3_bucket_name = config.get("s3_bucket", DEFAULT_S3_BUCKET)
        self._s3_bucket_exists = False
        # https://github.com/boto/boto3/issues/259
        self.db.meta.client.meta.events.unregister('before-sign.s3', fix_s3_host)

    def report_timing(self, action):
        def record_long_request(duration):
            if duration > 30:
                notify_exception(None, "S3BlobDB request took a long time.", details={
                    'duration': duration,
                })

        return datadog_bucket_timer('commcare.blobs.requests.timing', tags=[
            'action:{}'.format(action),
            's3_bucket_name:{}'.format(self.s3_bucket_name)
        ], timing_buckets=(.03, .1, .3, 1, 3, 10, 30, 100), callback=record_long_request)

    def put(self, content, identifier, bucket=DEFAULT_BUCKET, timeout=None):
        path = self.get_path(identifier, bucket)
        s3_bucket = self._s3_bucket(create=True)
        if isinstance(content, BlobStream) and content.blob_db is self:
            source = {"Bucket": self.s3_bucket_name, "Key": content.blob_path}
            s3_bucket.copy(source, path)
            obj = s3_bucket.Object(path)
            # unfortunately cannot get content-md5 here
            return BlobInfo(identifier, obj.content_length, None)
        content.seek(0)
        content_md5 = get_content_md5(content)
        content_length = get_file_size(content)
        with self.report_timing('put'):
            s3_bucket.upload_fileobj(content, path)
        if timeout is not None:
            set_blob_expire_object(bucket, identifier, content_length, timeout)
        datadog_counter('commcare.blobs.added.count')
        datadog_counter('commcare.blobs.added.bytes', value=content_length)
        return BlobInfo(identifier, content_length, "md5-" + content_md5)

    def get(self, identifier, bucket=DEFAULT_BUCKET):
        path = self.get_path(identifier, bucket)
        with maybe_not_found(throw=NotFound(identifier, bucket)), \
                self.report_timing('get'):
            resp = self._s3_bucket().Object(path).get()
        return BlobStream(resp["Body"], self, path)

    def size(self, identifier, bucket=DEFAULT_BUCKET):
        path = self.get_path(identifier, bucket)
        with maybe_not_found(throw=NotFound(identifier, bucket)), \
                self.report_timing('size'):
            return self._s3_bucket().Object(path).content_length

    def exists(self, identifier, bucket=DEFAULT_BUCKET):
        path = self.get_path(identifier, bucket)
        try:
            with maybe_not_found(throw=NotFound(identifier, bucket)), \
                    self.report_timing('exists'):
                self._s3_bucket().Object(path).load()
            return True
        except NotFound:
            return False

    def delete(self, *args, **kw):
        identifier, bucket = self.get_args_for_delete(*args, **kw)
        path = self.get_path(identifier, bucket)
        s3_bucket = self._s3_bucket()
        with maybe_not_found():
            success = True
            if identifier is None:
                summaries = s3_bucket.objects.filter(Prefix=path + "/")
                pages = ([{"Key": o.key} for o in page]
                         for page in summaries.pages())
                deleted_bytes = sum(o.size for page in summaries.pages()
                                    for o in page)
                deleted_count = 0
                for objects in pages:
                    resp = s3_bucket.delete_objects(Delete={"Objects": objects})
                    deleted = set(d["Key"] for d in resp.get("Deleted", []))
                    success = success and all(o["Key"] in deleted for o in objects)
                    deleted_count += len(deleted)
            else:
                obj = s3_bucket.Object(path)
                deleted_count = 1
                # may raise a not found error -> return False
                deleted_bytes = obj.content_length
                obj.delete()
            datadog_counter('commcare.blobs.deleted.count', value=deleted_count)
            datadog_counter('commcare.blobs.deleted.bytes', value=deleted_bytes)
            return success
        return False

    def bulk_delete(self, paths):
        success = True
        for chunk in chunked(paths, 1000):
            objects = [{"Key": path} for path in chunk]
            s3_bucket = self._s3_bucket()
            deleted_bytes = 0
            for path in chunk:
                with maybe_not_found():
                    deleted_bytes += s3_bucket.Object(path).content_length
            resp = s3_bucket.delete_objects(Delete={"Objects": objects})
            deleted = set(d["Key"] for d in resp.get("Deleted", []))
            success = success and all(o["Key"] in deleted for o in objects)
            datadog_counter('commcare.blobs.deleted.count', value=len(deleted))
            datadog_counter('commcare.blobs.deleted.bytes', value=deleted_bytes)
        return success

    def copy_blob(self, content, info, bucket):
        self._s3_bucket(create=True)
        path = self.get_path(info.identifier, bucket)
        with self.report_timing('copy_blobdb'):
            self._s3_bucket().upload_fileobj(content, path)

    def _s3_bucket(self, create=False):
        if create and not self._s3_bucket_exists:
            try:
                self.db.meta.client.head_bucket(Bucket=self.s3_bucket_name)
            except ClientError as err:
                if not is_not_found(err):
                    datadog_counter('commcare.blobdb.notfound')
                    raise
                self.db.create_bucket(Bucket=self.s3_bucket_name)
            self._s3_bucket_exists = True
        return self.db.Bucket(self.s3_bucket_name)

    def get_path(self, identifier=None, bucket=DEFAULT_BUCKET):
        if identifier is None:
            return safepath(bucket)
        return safejoin(bucket, identifier)


class BlobStream(ClosingContextProxy):

    def __init__(self, stream, blob_db, blob_path):
        super(BlobStream, self).__init__(stream)
        self._blob_db = weakref.ref(blob_db)
        self.blob_path = blob_path

    @property
    def blob_db(self):
        return self._blob_db()


def safepath(path):
    if (path.startswith(("/", ".")) or
            "/../" in path or
            path.endswith("/..") or
            not SAFENAME.match(path)):
        raise BadName("unsafe path name: %r" % path)
    return path


def safejoin(root, subpath):
    """Join root to subpath ensuring that the result is actually inside root
    """
    return safepath(root) + "/" + safepath(subpath)


def is_not_found(err, not_found_codes=["NoSuchKey", "NoSuchBucket", "404"]):
    return (err.response["Error"]["Code"] in not_found_codes or
        err.response.get("Errors", {}).get("Error", {}).get("Code") in not_found_codes)


def get_content_md5(content):
    params = {"body": content, "headers": {}}
    calculate_md5(params)
    return params["headers"]["Content-MD5"]


def get_file_size(fileobj):

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
            datadog_counter('commcare.blobdb.notfound')
            raise
        if throw is not None:
            raise throw
