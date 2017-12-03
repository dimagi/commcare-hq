from __future__ import unicode_literals
from __future__ import absolute_import
from io import StringIO

from testil import replattr

import corehq.blobs.migratingdb as mod
from corehq.blobs import DEFAULT_BUCKET
from corehq.blobs.tests.util import (
    get_id,
    TemporaryFilesystemBlobDB,
    TemporaryMigratingBlobDB,
    TemporaryS3BlobDB,
)


def get_base_class():
    # HACK prevent this module from running tests on TestS3BlobDB
    from corehq.blobs.tests.test_s3db import TestS3BlobDB
    return TestS3BlobDB


class TestMigratingBlobDB(get_base_class()):

    @classmethod
    def setUpClass(cls):
        super(TestMigratingBlobDB, cls).setUpClass()
        assert isinstance(cls.db, TemporaryS3BlobDB), cls.db
        cls.s3db = cls.db
        cls.fsdb = TemporaryFilesystemBlobDB()
        cls.db = TemporaryMigratingBlobDB(cls.s3db, cls.fsdb)

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
