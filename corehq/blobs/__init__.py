from .exceptions import Error, NotFound  # noqa: F401

_db = []  # singleton/global, stack for tests to push temporary dbs


def get_blob_db():
    if not _db:
        from django.conf import settings
        db = _get_s3_db(settings)
        if db is None:
            db = _get_fs_db(settings)
        elif getattr(settings, "BLOB_DB_MIGRATING_FROM_FS_TO_S3", False):
            db = _get_migrating_db(db, _get_fs_db(settings))
        elif getattr(settings, "BLOB_DB_MIGRATING_FROM_S3_TO_S3", False):
            db = _get_migrating_db(db, _get_s3_db(settings, "OLD_S3_BLOB_DB_SETTINGS"))
        _db.append(db)
    return _db[-1]


def _get_s3_db(settings, key="S3_BLOB_DB_SETTINGS"):
    from .s3db import S3BlobDB
    config = getattr(settings, key, None)
    return None if config is None else S3BlobDB(config)


def _get_fs_db(settings):
    from .fsdb import FilesystemBlobDB
    blob_dir = settings.SHARED_DRIVE_CONF.blob_dir
    if blob_dir is None:
        reason = settings.SHARED_DRIVE_CONF.get_unset_reason("blob_dir")
        raise Error("cannot initialize blob db: %s" % reason)
    return FilesystemBlobDB(blob_dir)


def _get_migrating_db(new_db, old_db):
    from .migratingdb import MigratingBlobDB
    return MigratingBlobDB(new_db, old_db)


class CODES:
    """Blob type codes.

    A unique blob type code should be assigned to each new area of HQ
    that will have blobs associated with it. This is mainly intended for
    analysis purposes (how much blob storage is used per type code?),
    although it is also useful when debugging to trace a blob identifier
    back to its parent.

    When adding codes for new models, always use a unique code that has
    never been used before, preferably one more than the highest
    existing code. Once a type code has been used it should never be
    reused for another purpose.

    Each type code associated with couch documents should only reference
    document types living in a single couch database or SQL models with
    non-overlapping primary keys. `MetaDB.get` and related methods as
    well as tools like the `check_blob_logs` management command will not
    function properly if this contract is broken.
    """
    # used to get stored blob bytes (no blobs should have this type)
    maybe_compressed = -1

    _default = 0        # legacy, do not use

    tempfile = 1

    form_xml = 2
    form_attachment = 3

    domain = 4          # Domain
    application = 5     # Application, Application-Deleted, LinkedApplication
    multimedia = 6      # CommCareMultimedia
    commcarebuild = 7   # CommCareBuild
    data_import = 8     # case_importer

    data_export = 9     # FormExportInstance, CaseExportInstance
    basic_export = 10   # SavedBasicExport (obsolete)

    invoice = 11        # InvoicePdf
    restore = 12
    fixture = 13        # domain-fixtures
    demo_user_restore = 14  # DemoUserRestore
    data_file = 15      # domain data file (see DataFile class)
    form_multimedia = 16     # form submission multimedia zip
    email_multimedia = 17    # email images and attachments


CODES.name_of = {code: name
    for name, code in vars(CODES).items() if isinstance(code, int)}.get
