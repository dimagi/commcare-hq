from __future__ import unicode_literals
from StringIO import StringIO

from django.conf import settings
from testil import replattr

import corehq.blobs.migratingdb as mod
from corehq.blobs import DEFAULT_BUCKET
from corehq.blobs.tests.util import get_id, TemporaryS3BlobDB, TemporaryFilesystemBlobDB
from corehq.util.test_utils import trap_extra_setup


def get_base_class():
    # HACK prevent this module from running tests on TestS3BlobDB
    from corehq.blobs.tests.test_s3db import TestS3BlobDB
    return TestS3BlobDB


class TestMigratingBlobDB(get_base_class()):

    @classmethod
    def setUpClass(cls):
        with trap_extra_setup(AttributeError, msg="S3_BLOB_DB_SETTINGS not configured"):
            config = settings.S3_BLOB_DB_SETTINGS
        cls.s3db = TemporaryS3BlobDB(config)
        cls.fsdb = TemporaryFilesystemBlobDB()
        cls.db = mod.MigratingBlobDB(cls.s3db, cls.fsdb)

    @classmethod
    def tearDownClass(cls):
        cls.fsdb.close()
        cls.s3db.close()

    def test_fall_back_to_fsdb(self):
        info = self.fsdb.put(StringIO(b"content"), get_id())
        with self.db.get(info.identifier) as fh:
            self.assertEqual(fh.read(), b"content")

    def test_copy_blob_masks_old_blob(self):
        content = StringIO(b"fs content")
        info = self.fsdb.put(content, get_id())
        content.seek(0)
        self.db.copy_blob(content, info, DEFAULT_BUCKET)
        self.assertEndsWith(
            self.fsdb.get_path(info.identifier), "/" + self.db.get_path(info.identifier))
        with replattr(self.fsdb, "get", blow_up, sigcheck=False):
            with self.assertRaises(Boom):
                self.fsdb.get(info.identifier)
            with self.db.get(info.identifier) as fh:
                self.assertEqual(fh.read(), b"fs content")

    def test_delete_from_both_fs_and_s3(self):
        info = self.fsdb.put(StringIO(b"content"), get_id())
        with self.fsdb.get(info.identifier) as content:
            self.db.copy_blob(content, info, DEFAULT_BUCKET)
        self.assertTrue(self.db.delete(info.identifier))
        with self.assertRaises(mod.NotFound):
            self.db.get(info.identifier)

    def assertEndsWith(self, a, b):
        assert a.endswith(b), (a, b)


class Boom(Exception):
    pass


def blow_up(*args, **kw):
    raise Boom("should not be called")
