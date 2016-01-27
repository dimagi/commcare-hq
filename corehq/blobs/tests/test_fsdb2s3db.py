from __future__ import unicode_literals
from os.path import join
from unittest import TestCase
from StringIO import StringIO

from django.conf import settings
from testil import replattr

import corehq.blobs.fsdb2s3db as mod
from corehq.blobs.tests.util import TemporaryS3BlobDB, TemporaryFilesystemBlobDB
from corehq.util.test_utils import generate_cases, trap_extra_setup


def get_base_class():
    # HACK prevent this class from running tests on TestS3BlobDB
    from corehq.blobs.tests.test_s3db import TestS3BlobDB
    return TestS3BlobDB


class TestFsToS3BlobDB(get_base_class()):

    @classmethod
    def setUpClass(cls):
        with trap_extra_setup(AttributeError, msg="S3_BLOB_DB_SETTINGS not configured"):
            config = settings.S3_BLOB_DB_SETTINGS
        cls.s3db = TemporaryS3BlobDB(config)
        cls.fsdb = TemporaryFilesystemBlobDB()
        cls.db = mod.FsToS3BlobDB(cls.s3db, cls.fsdb)

    @classmethod
    def tearDownClass(cls):
        cls.fsdb.close()
        cls.s3db.close()

    def test_fall_back_to_fsdb(self):
        info = self.fsdb.put(StringIO(b"content"), "test")
        with self.db.get(info.name) as fh:
            self.assertEqual(fh.read(), b"content")

    def test_copy_to_s3_masks_fsdb_blob(self):
        # techincally this is an impossible scenario since fsdb should
        # always have the same content as s3db after copy_to_s3
        info = self.fsdb.put(StringIO(b"fs content"), "test")
        get = lambda *a: ContextualStringIO(b"s3 content")
        with replattr(self.fsdb, "get", get, sigcheck=False):
            s3_obj = self.db.copy_to_s3(info, mod.DEFAULT_BUCKET)
        self.assertEndsWith(
            self.fsdb.get_path(info.name), "/" + self.db.get_path(info.name))
        self.assertEqual(s3_obj.content_length, info.length)
        with self.db.get(info.name) as fh:
            self.assertEqual(fh.read(), b"s3 content")

    def test_delete_from_both_fs_and_s3(self):
        name = "test"
        info = self.fsdb.put(StringIO(b"content"), "test")
        self.db.copy_to_s3(info, mod.DEFAULT_BUCKET)
        self.assertTrue(self.db.delete(info.name))
        with self.assertRaises(mod.NotFound):
            self.db.get(info.name)

    # TODO investigate if put should delete blob in fsdb

    def assertEndsWith(self, a, b):
        assert a.endswith(b), (a, b)

class ContextualStringIO(StringIO):

    def __enter__(self):
        return self

    def __exit__(self, *args, **kw):
        pass
