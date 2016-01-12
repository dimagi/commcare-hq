from __future__ import unicode_literals
from os.path import join
from unittest import TestCase, SkipTest
from StringIO import StringIO

from django.conf import settings

import corehq.blobs.s3db as mod
from corehq.blobs.tests.util import TemporaryS3BlobDB
from corehq.util.test_utils import generate_cases


class TestS3BlobDB(TestCase):

    @classmethod
    def setUpClass(cls):
        s3_settings = getattr(settings, "S3_BLOB_DB_SETTINGS", None)
        if s3_settings is None:
            raise SkipTest("S3_BLOB_DB_SETTINGS not configured")
        cls.db = TemporaryS3BlobDB(s3_settings)

    @classmethod
    def tearDownClass(cls):
        cls.db.close()

    def test_put_and_get(self):
        name = "test.1"
        info = self.db.put(StringIO(b"content"), name)
        with self.db.get(info.name) as fh:
            self.assertEqual(fh.read(), b"content")

    def test_put_and_get_with_unicode_names(self):
        name = "test.\u4500"
        bucket = "doc.4500"
        info = self.db.put(StringIO(b"content"), name, bucket)
        with self.db.get(info.name, bucket) as fh:
            self.assertEqual(fh.read(), b"content")

    def test_put_and_get_with_bucket(self):
        name = "test.2"
        bucket = "doc.2"
        info = self.db.put(StringIO(b"content"), name, bucket)
        with self.db.get(info.name, bucket) as fh:
            self.assertEqual(fh.read(), b"content")

    def test_put_with_bucket_and_get_without_bucket(self):
        name = "test.3"
        bucket = "doc.3"
        info = self.db.put(StringIO(b"content"), name, bucket)
        with self.assertRaises(mod.NotFound):
            self.db.get(info.name)

    def test_delete(self):
        name = "test.4"
        bucket = "doc.4"
        info = self.db.put(StringIO(b"content"), name, bucket)

        self.assertTrue(self.db.delete(info.name, bucket), 'delete failed')

        with self.assertRaises(mod.NotFound):
            self.db.get(info.name, bucket)

        # boto3 client reports that the object was deleted even if there was
        # no object to delete
        #self.assertFalse(self.db.delete(info.name, bucket), 'delete should fail')

    def test_delete_bucket(self):
        bucket = join("doctype", "ys7v136b")
        info = self.db.put(StringIO(b"content"), bucket=bucket)
        self.assertTrue(self.db.delete(bucket=bucket))

        self.assertTrue(info.name)
        with self.assertRaises(mod.NotFound):
            self.db.get(info.name, bucket=bucket)


@generate_cases([
    ("test.1", "\u4500.1"),
    ("test.1", "/tmp/notallowed"),
    ("test.1", "."),
    ("test.1", ".."),
    ("test.1", "../notallowed"),
    ("test.1", "notallowed/.."),
    ("/test.1",),
    ("../test.1",),
], TestS3BlobDB)
def test_bad_name(self, name, bucket=mod.DEFAULT_BUCKET):
    with self.assertRaises(mod.BadName):
        self.db.get(name, bucket)
