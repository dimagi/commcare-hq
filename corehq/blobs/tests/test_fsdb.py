from __future__ import unicode_literals
import os
from hashlib import md5
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
        self.db.put(StringIO(b"content"), name)
        with self.db.get(name) as fh:
            self.assertEqual(fh.read(), b"content")

    def test_put_and_get_with_unicode_names(self):
        name = "test.\u4500"
        bucket = "doc.4500"
        self.db.put(StringIO(b"content"), name, bucket)
        with self.db.get(name, bucket) as fh:
            self.assertEqual(fh.read(), b"content")

    def test_put_and_get_with_bucket(self):
        name = "test.2"
        bucket = "doc.2"
        self.db.put(StringIO(b"content"), name, bucket)
        with self.db.get(name, bucket) as fh:
            self.assertEqual(fh.read(), b"content")

    def test_put_with_bucket_and_get_without_bucket(self):
        name = "test.3"
        bucket = "doc.3"
        self.db.put(StringIO(b"content"), name, bucket)
        with self.assertRaises(mod.NotFound):
            self.db.get(name)

    def test_delete(self):
        name = "test.4"
        bucket = "doc.4"
        self.db.put(StringIO(b"content"), name, bucket)

        assert self.db.delete(name, bucket), 'delete failed'

        with self.assertRaises(mod.NotFound):
            self.db.get(name, bucket)

        assert not self.db.delete(name, bucket), 'delete should fail'

    def test_delete_bucket(self):
        name = "test.1"
        bucket = join("doctype", "ys7v136b")
        self.db.put(StringIO(b"content"), name, bucket)
        assert self.db.delete(bucket=bucket)

        names = os.listdir(join(self.rootdir, "doctype"))
        assert "ys7v136b" not in names, "bucket not deleted"

    def test_bucket_path(self):
        name = "test.1"
        bucket = join("doctype", "8cd98f0")
        self.db.put(StringIO(b"content"), name, bucket)
        path = join(self.rootdir, bucket)
        assert isdir(path), path
        assert os.listdir(path)

    def test_safe_attachment_path(self):
        name = "test.1"
        bucket = join("doctype", "8cd98f0")
        self.db.put(StringIO(b"content"), name, bucket)
        path = join(self.rootdir, bucket, name + "." + md5(name).hexdigest())
        with open(path, "rb") as fh:
            self.assertEqual(fh.read(), b"content")

    def test_unsafe_attachment_path(self):
        name = "\u4500.1"
        bucket = join("doctype", "8cd98f0")
        self.db.put(StringIO(b"content"), name, bucket)
        path = join(self.rootdir, bucket, "unsafe." + md5(name.encode("utf-8")).hexdigest())
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
