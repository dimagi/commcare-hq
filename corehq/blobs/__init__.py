from .exceptions import Error
_db = []  # singleton/global, stack for tests to push temporary dbs


def get_blob_db():
    if not _db:
        from .fsdb import FilesystemBlobDB
        from django.conf import settings
        blob_dir = settings.SHARED_DRIVE_CONF.blob_dir
        if blob_dir is None:
            reason = settings.SHARED_DRIVE_CONF.get_unset_reason("blob_dir")
            raise Error("cannot initialize blob db: %s" % reason)
        _db.append(FilesystemBlobDB(blob_dir))
    return _db[-1]
