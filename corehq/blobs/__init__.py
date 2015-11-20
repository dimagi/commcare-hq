_db = []  # singleton/global, stack for tests to push temporary dbs


def get_blob_db():
    if not _db:
        from .fsdb import FilesystemBlobDB
        from django.conf import settings
        _db.append(FilesystemBlobDB(settings.SHARED_DRIVE_CONF.blob_dir))
    return _db[-1]
