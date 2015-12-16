from __future__ import unicode_literals
import os
from os.path import isdir, join
from shutil import rmtree
from tempfile import mkdtemp
from unittest import TestCase
from StringIO import StringIO

import corehq.blobs.fsdb as mod
from corehq.util.test_utils import generate_cases


class TestFilesystemBlobDB(TestCase):

    @classmethod
    def setUpClass(cls):
        cls.rootdir = mkdtemp(prefix="blobdb")
        cls.db = mod.FilesystemBlobDB(cls.rootdir)

    @classmethod
    def tearDownClass(cls):
        cls.db = None
        rmtree(cls.rootdir)
        cls.rootdir = None

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

        self.assertFalse(self.db.delete(info.name, bucket), 'delete should fail')

    def test_delete_bucket(self):
        bucket = join("doctype", "ys7v136b")
        self.db.put(StringIO(b"content"), bucket=bucket)
        self.assertTrue(self.db.delete(bucket=bucket))

        names = os.listdir(self.db.get_path(bucket="doctype"))
        self.assertNotIn("ys7v136b", names, "bucket not deleted")

    def test_bucket_path(self):
        bucket = join("doctype", "8cd98f0")
        self.db.put(StringIO(b"content"), bucket=bucket)
        path = self.db.get_path(bucket=bucket)
        self.assertTrue(isdir(path), path)
        self.assertTrue(os.listdir(path))

    def test_safe_attachment_path(self):
        name = "test.1"
        bucket = join("doctype", "8cd98f0")
        info = self.db.put(StringIO(b"content"), name, bucket)
        self.assertTrue(info.name.startswith(name + "."), info.name)
        path = self.db.get_path(info.name, bucket)
        with open(path, "rb") as fh:
            self.assertEqual(fh.read(), b"content")

    def test_unsafe_attachment_path(self):
        name = "\u4500.1"
        bucket = join("doctype", "8cd98f0")
        info = self.db.put(StringIO(b"content"), name, bucket)
        self.assertTrue(info.name.startswith("unsafe."), info.name)
        path = self.db.get_path(info.name, bucket)
        with open(path, "rb") as fh:
            self.assertEqual(fh.read(), b"content")

    def test_unsafe_attachment_name(self):
        name = "test/1"  # name with directory separator
        bucket = join("doctype", "8cd98f0")
        info = self.db.put(StringIO(b"content"), name, bucket)
        self.assertTrue(info.name.startswith("unsafe."), info.name)
        path = self.db.get_path(info.name, bucket)
        with open(path, "rb") as fh:
            self.assertEqual(fh.read(), b"content")

    def test_empty_attachment_name(self):
        info = self.db.put(StringIO(b"content"))
        self.assertNotIn(".", info.name)
        path = self.db.get_path(info.name)
        with open(path, "rb") as fh:
            self.assertEqual(fh.read(), b"content")


@generate_cases([
    ("test.1", "\u4500.1"),
    ("test.1", "/tmp/notallowed"),
    ("test.1", "."),
    ("test.1", ".."),
    ("test.1", "../notallowed"),
    ("test.1", "notallowed/.."),
    ("/test.1",),
    ("../test.1",),
], TestFilesystemBlobDB)
def test_bad_name(self, name, bucket=mod.DEFAULT_BUCKET):
    with self.assertRaises(mod.BadName):
        self.db.get(name, bucket)
