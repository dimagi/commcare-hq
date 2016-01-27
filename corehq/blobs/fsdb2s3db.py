"""Filesystem database for large binary data objects (blobs)
"""
from __future__ import absolute_import

from corehq.blobs import DEFAULT_BUCKET
from corehq.blobs.exceptions import BadName, NotFound


class FsToS3BlobDB(object):
    """Adaptor for migrating from FilesystemBlobDB to S3BlobDB"""

    def __init__(self, s3db, fsdb):
        self.s3db = s3db
        self.fsdb = fsdb

    def put(self, *args, **kw):
        return self.s3db.put(*args, **kw)

    def get(self, *args, **kw):
        try:
            return self.s3db.get(*args, **kw)
        except NotFound:
            return self.fsdb.get(*args, **kw)

    def delete(self, *args, **kw):
        s3_result = self.s3db.delete(*args, **kw)
        fs_result = self.fsdb.delete(*args, **kw)
        return s3_result or fs_result

    def get_path(self, *args, **kw):
        return self.s3db.get_path(*args, **kw)

    def copy_to_s3(self, info, bucket, _test_content=None):
        assert info.digest.startswith('md5-'), info
        content_md5 = info.digest[4:]
        content = self.fsdb.get(info.name, bucket)
        with content:
            return self.s3db._s3_bucket(create=True).put_object(
                Key=self.s3db.get_path(info.name, bucket),
                Body=content,
                ContentMD5=content_md5,
            )
