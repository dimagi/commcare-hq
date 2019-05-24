from __future__ import absolute_import
from __future__ import unicode_literals
from shutil import rmtree
from tempfile import mkdtemp
from uuid import uuid4
from contextlib import contextmanager

from django.conf import settings

import corehq.blobs as blobs
from corehq.blobs.fsdb import FilesystemBlobDB
from corehq.blobs.models import BlobMeta, DeletedBlobMeta
from corehq.blobs.s3db import S3BlobDB
from corehq.blobs.migratingdb import MigratingBlobDB
from corehq.blobs.util import random_url_id
from corehq.sql_db.util import (
    get_db_alias_for_partitioned_doc,
    get_db_aliases_for_partitioned_query,
)


def get_id():
    return random_url_id(8)


def new_meta(**kw):
    kw.setdefault("domain", "test")
    kw.setdefault("parent_id", "test")
    kw.setdefault("type_code", blobs.CODES.form_xml)
    return BlobMeta(**kw)


def get_meta(meta, deleted=False):
    """Fetch a new copy of the given metadata from the database"""
    db = get_db_alias_for_partitioned_doc(meta.parent_id)
    if deleted:
        return DeletedBlobMeta.objects.using(db).get(id=meta.id)
    return BlobMeta.objects.using(db).get(id=meta.id)


@contextmanager
def temporary_blob_db(db):
    """Temporarily install the given blob db globally

    `get_blob_db()` will return the given blob db until the context
    manager exits.
    """
    blobs._db.append(db)
    try:
        assert blobs.get_blob_db() is db, 'got wrong blob db'
        yield
    finally:
        blobs._db.remove(db)


class TemporaryBlobDBMixin(object):
    """Create temporary blob db and install as global blob db

    Global blob DB can be retrieved with `corehq.blobs.get_blob_db()`
    """

    def __init__(self, *args, **kw):
        super(TemporaryBlobDBMixin, self).__init__(*args, **kw)

        blobs._db.append(self)
        try:
            # verify get_blob_db() returns our new db
            assert blobs.get_blob_db() is self, 'got wrong blob db'
        except:
            self.close()
            raise

    def close(self):
        try:
            blobs._db.remove(self)
        finally:
            self.clean_db()

    def clean_db(self):
        if settings.USE_PARTITIONED_DATABASE:
            # partitioned databases are in autocommit mode, and django's
            # per-test transaction does not roll back changes there, so
            # blob metadata needs to be cleaned up here
            for dbname in get_db_aliases_for_partitioned_query():
                BlobMeta.objects.using(dbname).all().delete()

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        self.close()


class TemporaryFilesystemBlobDB(TemporaryBlobDBMixin, FilesystemBlobDB):

    def __init__(self):
        rootdir = mkdtemp(prefix="blobdb")
        super(TemporaryFilesystemBlobDB, self).__init__(rootdir)

    def clean_db(self):
        super(TemporaryFilesystemBlobDB, self).clean_db()
        rmtree(self.rootdir)
        self.rootdir = None


class TemporaryS3BlobDB(TemporaryBlobDBMixin, S3BlobDB):

    def __init__(self, config):
        name_parts = ["test", config.get("s3_bucket", "blobdb"), uuid4().hex]
        config = dict(config)
        config["s3_bucket"] = "-".join(name_parts)
        super(TemporaryS3BlobDB, self).__init__(config)
        assert self.s3_bucket_name == config["s3_bucket"], \
            (self.s3_bucket_name, config)

    def clean_db(self):
        if not self._s3_bucket_exists:
            return
        super(TemporaryS3BlobDB, self).clean_db()
        assert self.s3_bucket_name.startswith("test-"), self.s3_bucket_name
        s3_bucket = self._s3_bucket()
        summaries = s3_bucket.objects.all()
        for page in summaries.pages():
            objects = [{"Key": o.key} for o in page]
            s3_bucket.delete_objects(Delete={"Objects": objects})
        s3_bucket.delete()


class TemporaryMigratingBlobDB(TemporaryBlobDBMixin, MigratingBlobDB):

    def __init__(self, *args):
        for arg in args:
            assert isinstance(arg, TemporaryBlobDBMixin), arg
        super(TemporaryMigratingBlobDB, self).__init__(*args)

    def clean_db(self):
        self.old_db.close()
        self.new_db.close()
