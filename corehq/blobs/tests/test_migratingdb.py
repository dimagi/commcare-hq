from __future__ import unicode_literals
from os.path import join
from unittest import TestCase
from StringIO import StringIO

from django.conf import settings
from testil import replattr

import corehq.blobs.migratingdb as mod
from corehq.blobs.tests.util import TemporaryS3BlobDB, TemporaryFilesystemBlobDB
from corehq.util.test_utils import generate_cases, trap_extra_setup


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
        info = self.fsdb.put(StringIO(b"content"), "test")
        with self.db.get(info.name) as fh:
            self.assertEqual(fh.read(), b"content")

    def test_copy_blob_masks_old_blob(self):
        # techincally this is an impossible scenario since fsdb should
        # always have the same content as s3db after copy_blob
        info = self.fsdb.put(StringIO(b"fs content"), "test")
        self.db.copy_blob(StringIO(b"s3 content"), info, mod.DEFAULT_BUCKET)
        self.assertEndsWith(
            self.fsdb.get_path(info.name), "/" + self.db.get_path(info.name))
        with self.db.get(info.name) as fh:
            self.assertEqual(fh.read(), b"s3 content")

    def test_delete_from_both_fs_and_s3(self):
        name = "test"
        info = self.fsdb.put(StringIO(b"content"), "test")
        with self.fsdb.get(info.name) as content:
            self.db.copy_blob(content, info, mod.DEFAULT_BUCKET)
        self.assertTrue(self.db.delete(info.name))
        with self.assertRaises(mod.NotFound):
            self.db.get(info.name)

    def assertEndsWith(self, a, b):
        assert a.endswith(b), (a, b)
