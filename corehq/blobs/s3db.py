from __future__ import absolute_import
import re
from uuid import uuid4

from corehq.blobs import BlobInfo, DEFAULT_BUCKET
from corehq.blobs.exceptions import BadName, NotFound

import boto3
from botocore.handlers import calculate_md5
from botocore.exceptions import ClientError
from botocore.utils import fix_s3_host

DEFAULT_S3_BUCKET = "blobdb"
SAFENAME = re.compile("^[a-z0-9_./-]+$", re.IGNORECASE)


class S3BlobDB(object):

    def __init__(self, config):
        self.db = boto3.resource(
            's3',
            endpoint_url=config.get("url"),
            aws_access_key_id=config.get("access_key", ""),
            aws_secret_access_key=config.get("secret_key", ""),
        )
        self.s3_bucket_name = config.get("s3_bucket", DEFAULT_S3_BUCKET)
        self._s3_bucket_exists = False
        # https://github.com/boto/boto3/issues/259
        self.db.meta.client.meta.events.unregister('before-sign.s3', fix_s3_host)

    def put(self, content, basename="", bucket=DEFAULT_BUCKET, content_md5=None):
        """Put a blob in persistent storage

        :param content: A file-like object in binary read mode.
        :param basename: Optional name from which the blob name will be
        derived. This is used to make the unique blob name somewhat
        recognizable.
        :param bucket: Optional bucket name used to partition blob data
        in the persistent storage medium. This may be delimited with
        slashes (/). It must be a valid relative path.
        :param content_md5: RFC-1864-compliant Content-MD5 header value.
        If this parameter is omitted or its value is `None` then content
        must be a seekable file-like object. NOTE: the value should not
        be prefixed with `md5-` even though we store it that way.
        :returns: A `BlobInfo` named tuple. The returned object has a
        `name` member that must be used to get or delete the blob. It
        should not be confused with the optional `basename` parameter.
        """
        name = self.get_unique_name(basename)
        path = self.get_path(name, bucket)
        if content_md5 is None:
            params = {"body": content, "headers": {}}
            calculate_md5(params)
            content_md5 = params["headers"]["Content-MD5"]
        obj = self._s3_bucket(create=True).put_object(
            Key=path,
            Body=content,
            ContentMD5=content_md5,
        )
        return BlobInfo(name, obj.content_length, "md5-" + content_md5)

    def get(self, name, bucket=DEFAULT_BUCKET):
        """Get a blob

        :param name: The name of the object to get.
        :param bucket: Optional bucket name. This must have the same
        value that was passed to ``put``.
        :raises: `NotFound` if the object does not exist.
        :returns: A file-like object in binary read mode. The returned
        object should be closed when finished reading.
        """
        path = self.get_path(name, bucket)
        try:
            resp = self._s3_bucket().Object(path).get()
        except ClientError as err:
            if is_not_found(err):
                raise NotFound(name, bucket)
            raise
        return ClosingContextProxy(resp["Body"])  # body stream

    def delete(self, name=None, bucket=DEFAULT_BUCKET):
        """Delete a blob

        :param name: The name of the object to be deleted. The entire
        bucket will be deleted if this is not specified.
        :param bucket: Optional bucket name. This must have the same
        value that was passed to ``put``.
        :returns: True if the blob was deleted else false.
        """
        path = self.get_path(name, bucket)
        success = True
        s3_bucket = self._s3_bucket()
        try:
            if name is None:
                summaries = s3_bucket.objects.filter(Prefix=path + "/")
                pages = ([{"Key": o.key} for o in page]
                         for page in summaries.pages())
            else:
                pages = [[{"Key": path}]]
            for objects in pages:
                resp = s3_bucket.delete_objects(Delete={"Objects": objects})
                if success:
                    deleted = set(d["Key"] for d in resp.get("Deleted", []))
                    success = all(o["Key"] in deleted for o in objects)
        except ClientError as err:
            if not is_not_found(err):
                raise
            success = False
        return success

    def copy_blob(self, content, info, bucket):
        """Copy blob from other blob database

        :param content: File-like blob content object.
        :param info: `BlobInfo` object.
        :param bucket: Bucket name.
        """
        if info.digest and info.digest.startswith("md5-"):
            content_md5 = info.digest[4:]
        else:
            params = {"body": content, "headers": {}}
            calculate_md5(params)
            content_md5 = params["headers"]["Content-MD5"]
        self._s3_bucket(create=True).put_object(
            Key=self.get_path(info.name, bucket),
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

    @staticmethod
    def get_unique_name(basename):
        if not basename:
            return uuid4().hex
        if SAFENAME.match(basename) and "/" not in basename:
            prefix = basename
        else:
            prefix = "unsafe"
        return prefix + "." + uuid4().hex

    def get_path(self, name=None, bucket=DEFAULT_BUCKET):
        if name is None:
            return safepath(bucket)
        return safejoin(bucket, name)


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


class ClosingContextProxy(object):

    def __init__(self, obj):
        self.obj = obj

    def __getattr__(self, name):
        return getattr(self.obj, name)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.obj.close()
