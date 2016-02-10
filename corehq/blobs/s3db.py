from __future__ import absolute_import
from contextlib import contextmanager

from corehq.blobs import BlobInfo, DEFAULT_BUCKET
from corehq.blobs.exceptions import BadName, NotFound

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

    def put(self, content, basename="", bucket=DEFAULT_BUCKET):
        identifier = self.get_identifier(basename)
        path = self.get_path(identifier, bucket)
        content_md5 = get_content_md5(content)
        obj = self._s3_bucket(create=True).put_object(
            Key=path,
            Body=content,
            ContentMD5=content_md5,
        )
        return BlobInfo(identifier, obj.content_length, "md5-" + content_md5)

    def get(self, identifier, bucket=DEFAULT_BUCKET):
        path = self.get_path(identifier, bucket)
        with maybe_not_found(throw=NotFound(identifier, bucket)):
            resp = self._s3_bucket().Object(path).get()
        return ClosingContextProxy(resp["Body"])  # body stream

    def delete(self, identifier=None, bucket=DEFAULT_BUCKET):
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

    def copy_blob(self, content, info, bucket):
        if info.digest and info.digest.startswith("md5-"):
            content_md5 = info.digest[4:]
        else:
            content_md5 = get_content_md5(content)
        self._s3_bucket(create=True).put_object(
            Key=self.get_path(info.identifier, bucket),
            Body=content,
            ContentMD5=content_md5,
        )

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


def safepath(path):
    if path.startswith(("/", ".")) or ".." in path or not SAFENAME.match(path):
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


@contextmanager
def maybe_not_found(throw=None):
    try:
        yield
    except ClientError as err:
        if not is_not_found(err):
            raise
        if throw is not None:
            raise throw


class ClosingContextProxy(object):

    def __init__(self, obj):
        self.obj = obj

    def __getattr__(self, name):
        return getattr(self.obj, name)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.obj.close()
