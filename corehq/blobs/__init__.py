from collections import namedtuple

from .exceptions import Error

DEFAULT_BUCKET = "_default"
_db = []  # singleton/global, stack for tests to push temporary dbs


def get_blob_db():
    if not _db:
        from django.conf import settings
        db = _get_s3_db(settings)
        if db is None:
            db = _get_fs_db(settings)
        elif getattr(settings, "BLOB_DB_MIGRATING_FROM_FS_TO_S3", False):
            from .migratingdb import MigratingBlobDB
            db = MigratingBlobDB(db, _get_fs_db(settings))
        _db.append(db)
    return _db[-1]


def _get_s3_db(settings):
    from .s3db import S3BlobDB
    config = getattr(settings, "S3_BLOB_DB_SETTINGS", None)
    return None if config is None else S3BlobDB(config)


def _get_fs_db(settings):
    from .fsdb import FilesystemBlobDB
    blob_dir = settings.SHARED_DRIVE_CONF.blob_dir
    if blob_dir is None:
        reason = settings.SHARED_DRIVE_CONF.get_unset_reason("blob_dir")
        raise Error("cannot initialize blob db: %s" % reason)
    return FilesystemBlobDB(blob_dir)


class BlobInfo(namedtuple("BlobInfo", ["identifier", "length", "digest"])):
    @property
    def md5_hash(self):
        if self.digest and self.digest.startswith("md5-"):
            return self.digest[4:]
