from collections import namedtuple

from .exceptions import Error

_db = []  # singleton/global, stack for tests to push temporary dbs


def get_blob_db():
    if not _db:
        from .fsdb import FilesystemBlobDB
        from .s3db import S3BlobDB
        from django.conf import settings
        s3_host = getattr(settings, "RIAK_CS_BLOB_DB_HOST", None)
        if s3_host is None:
            blob_dir = settings.SHARED_DRIVE_CONF.blob_dir
            if blob_dir is None:
                reason = settings.SHARED_DRIVE_CONF.get_unset_reason("blob_dir")
                raise Error("cannot initialize blob db: %s" % reason)

            def db_factory():
                return FilesystemBlobDB(blob_dir)
        else:
            def db_factory():
                return S3BlobDB(
                    s3_host,
                    getattr(settings, "S3_BLOB_DB_PORT", 8080)
                )
        _db.append(db_factory())
    return _db[-1]


BlobInfo = namedtuple("BlobInfo", ["name", "length", "digest"])
