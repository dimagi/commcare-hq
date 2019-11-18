from io import BytesIO

from testil import replattr

import corehq.blobs.migratingdb as mod
from corehq.blobs.tests.util import (
    new_meta,
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
        meta = self.fsdb.put(BytesIO(b"content"), meta=new_meta())
        with self.db.get(key=meta.key) as fh:
            self.assertEqual(fh.read(), b"content")

    def test_copy_blob_masks_old_blob(self):
        content = BytesIO(b"fs content")
        meta = self.fsdb.put(content, meta=new_meta())
        content.seek(0)
        self.db.copy_blob(content, key=meta.key)
        self.assertEndsWith(self.fsdb.get_path(key=meta.key), "/" + meta.key)
        with replattr(self.fsdb, "get", blow_up, sigcheck=False):
            with self.assertRaises(Boom):
                self.fsdb.get(key=meta.key)
            with self.db.get(key=meta.key) as fh:
                self.assertEqual(fh.read(), b"fs content")

    def test_delete_from_both_fs_and_s3(self):
        meta = self.fsdb.put(BytesIO(b"content"), meta=new_meta())
        with self.fsdb.get(key=meta.key) as content:
            self.db.copy_blob(content, key=meta.key)
        self.assertTrue(self.db.delete(key=meta.key))
        with self.assertRaises(mod.NotFound):
            self.db.get(key=meta.key)

    def assertEndsWith(self, a, b):
        assert a.endswith(b), (a, b)


class Boom(Exception):
    pass


def blow_up(*args, **kw):
    raise Boom("should not be called")
