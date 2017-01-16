from __future__ import absolute_import
import os
import weakref
from contextlib import contextmanager

from corehq.blobs import BlobInfo, DEFAULT_BUCKET
from corehq.blobs.exceptions import BadName, NotFound
from corehq.blobs.util import ClosingContextProxy

import boto3
from botocore.client import Config
from botocore.handlers import calculate_md5
from botocore.exceptions import ClientError
from botocore.utils import fix_s3_host

from corehq.blobs.interface import AbstractBlobDB, SAFENAME

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

    def put(self, content, identifier, bucket=DEFAULT_BUCKET):
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
        s3_bucket.upload_fileobj(content, path)
        return BlobInfo(identifier, content_length, "md5-" + content_md5)

    def get(self, identifier, bucket=DEFAULT_BUCKET):
        path = self.get_path(identifier, bucket)
        with maybe_not_found(throw=NotFound(identifier, bucket)):
            resp = self._s3_bucket().Object(path).get()
        return BlobStream(resp["Body"], self, path)

    def exists(self, identifier, bucket=DEFAULT_BUCKET):
        path = self.get_path(identifier, bucket)
        try:
            with maybe_not_found(throw=NotFound(identifier, bucket)):
                self._s3_bucket().Object(path).load()
            return True
        except NotFound:
            return False

    def delete(self, *args, **kw):
        identifier, bucket = self.get_args_for_delete(*args, **kw)
        path = self.get_path(identifier, bucket)
        s3_bucket = self._s3_bucket()
        with maybe_not_found():
            if identifier is None:
                summaries = s3_bucket.objects.filter(Prefix=path + "/")
                pages = ([{"Key": o.key} for o in page]
                         for page in summaries.pages())
            else:
                pages = [[{"Key": path}]]
            success = True
            for objects in pages:
                resp = s3_bucket.delete_objects(Delete={"Objects": objects})
                if success:
                    deleted = set(d["Key"] for d in resp.get("Deleted", []))
                    success = all(o["Key"] in deleted for o in objects)
            return success
        return False

    def bulk_delete(self, paths):
        objects = [{"Key": path} for path in paths]
        s3_bucket = self._s3_bucket()
        resp = s3_bucket.delete_objects(Delete={"Objects": objects})
        deleted = set(d["Key"] for d in resp.get("Deleted", []))
        success = all(o["Key"] in deleted for o in objects)
        return success

    def copy_blob(self, content, info, bucket):
        self._s3_bucket(create=True)
        path = self.get_path(info.identifier, bucket)
        self._s3_bucket().upload_fileobj(content, path)

    def _s3_bucket(self, create=False):
        if create and not self._s3_bucket_exists:
            try:
                self.db.meta.client.head_bucket(Bucket=self.s3_bucket_name)
            except ClientError as err:
                if not is_not_found(err):
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
        raise BadName(u"unsafe path name: %r" % path)
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
    if not hasattr(fileobj, 'fileno'):
        pos = fileobj.tell()
        try:
            fileobj.seek(0, os.SEEK_END)
            return fileobj.tell()
        finally:
            fileobj.seek(pos)
    return os.fstat(fileobj.fileno()).st_size


@contextmanager
def maybe_not_found(throw=None):
    try:
        yield
    except ClientError as err:
        if not is_not_found(err):
            raise
        if throw is not None:
            raise throw
