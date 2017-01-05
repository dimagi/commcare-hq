from __future__ import unicode_literals
import os
from os.path import isdir, join
from shutil import rmtree
from tempfile import mkdtemp
from unittest import TestCase
from StringIO import StringIO

import corehq.blobs.fsdb as mod
from corehq.blobs.exceptions import ArgumentError
from corehq.blobs.tests.util import get_id
from corehq.util.test_utils import generate_cases


class _BlobDBTests(object):

    def test_put_and_get(self):
        identifier = get_id()
        info = self.db.put(StringIO(b"content"), identifier)
        self.assertEqual(identifier, info.identifier)
        with self.db.get(info.identifier) as fh:
            self.assertEqual(fh.read(), b"content")

    def test_put_and_get_with_unicode_names(self):
        bucket = "doc.4500"
        info = self.db.put(StringIO(b"content"), get_id(), bucket=bucket)
        with self.db.get(info.identifier, bucket) as fh:
            self.assertEqual(fh.read(), b"content")

    def test_put_and_get_with_bucket(self):
        bucket = "doc.2"
        info = self.db.put(StringIO(b"content"), get_id(), bucket=bucket)
        with self.db.get(info.identifier, bucket) as fh:
            self.assertEqual(fh.read(), b"content")

    def test_put_with_bucket_and_get_without_bucket(self):
        bucket = "doc.3"
        info = self.db.put(StringIO(b"content"), get_id(), bucket=bucket)
        with self.assertRaises(mod.NotFound):
            self.db.get(info.identifier)

    def test_put_with_double_dotted_name(self):
        info = self.db.put(StringIO(b"content"), get_id())
        with self.db.get(info.identifier) as fh:
            self.assertEqual(fh.read(), b"content")

    def test_put_from_get_stream(self):
        old = self.db.put(StringIO(b"content"), get_id(), bucket="old_bucket")
        with self.db.get(old.identifier, "old_bucket") as fh:
            new = self.db.put(fh, get_id(), bucket="new_bucket")
        with self.db.get(new.identifier, "new_bucket") as fh:
            self.assertEqual(fh.read(), b"content")

    def test_exists(self):
        bucket = "doc.3.0"
        info = self.db.put(StringIO(b"content"), get_id(), bucket=bucket)
        self.assertTrue(self.db.exists(info.identifier, bucket), 'not found')

    def test_delete_not_exists(self):
        bucket = "doc.3.1"
        info = self.db.put(StringIO(b"content"), get_id(), bucket=bucket)
        self.db.delete(info.identifier, bucket)
        self.assertFalse(self.db.exists(info.identifier, bucket), 'not deleted')

    def test_delete(self):
        bucket = "doc.4"
        info = self.db.put(StringIO(b"content"), get_id(), bucket=bucket)

        self.assertTrue(self.db.delete(info.identifier, bucket), 'delete failed')

        with self.assertRaises(mod.NotFound):
            self.db.get(info.identifier, bucket)

        return info, bucket

    def test_bulk_delete(self):
        blobs = [
            ('test.5', 'doc.5'),
            ('test.6', 'doc.6'),
        ]
        infos = [
            self.db.put(StringIO(b"content-{}".format(blob[0])), get_id(), bucket=blob[1])
            for blob in blobs
        ]

        blob_infos = zip(blobs, infos)
        paths = [self.db.get_path(info.identifier, blob[1]) for blob, info in blob_infos]
        self.assertTrue(self.db.bulk_delete(paths), 'delete failed')

        for blob, info in blob_infos:
            with self.assertRaises(mod.NotFound):
                self.db.get(info.identifier, blob[1])

        return paths

    def test_delete_bucket(self):
        bucket = join("doctype", "ys7v136b")
        info = self.db.put(StringIO(b"content"), get_id(), bucket=bucket)
        self.assertTrue(self.db.delete(bucket=bucket))

        self.assertTrue(info.identifier)
        with self.assertRaises(mod.NotFound):
            self.db.get(info.identifier, bucket=bucket)

    def test_delete_identifier_in_default_bucket(self):
        info = self.db.put(StringIO(b"content"), get_id())
        self.assertTrue(self.db.delete(info.identifier), 'delete failed')
        with self.assertRaises(mod.NotFound):
            self.db.get(info.identifier)

    def test_delete_no_args(self):
        info = self.db.put(StringIO(b"content"), get_id())
        with self.assertRaises(ArgumentError):
            self.db.delete()
        # blobs in default bucket should not be deleted
        with self.db.get(info.identifier) as fh:
            self.assertEqual(fh.read(), b"content")
        self.assertTrue(self.db.delete(bucket=mod.DEFAULT_BUCKET))

    def test_prevent_delete_bucket_by_mistake(self):
        info = self.db.put(StringIO(b"content"), get_id())
        id_mistake = None
        with self.assertRaises(ArgumentError):
            self.db.delete(id_mistake, mod.DEFAULT_BUCKET)
        # blobs in default bucket should not be deleted
        with self.db.get(info.identifier) as fh:
            self.assertEqual(fh.read(), b"content")
        self.assertTrue(self.db.delete(bucket=mod.DEFAULT_BUCKET))

    def test_empty_attachment_name(self):
        info = self.db.put(StringIO(b"content"), get_id())
        self.assertNotIn(".", info.identifier)
        return info


@generate_cases([
    ("test.1", "\u4500.1"),
    ("test.1", "/tmp/notallowed"),
    ("test.1", "."),
    ("test.1", ".."),
    ("test.1", "../notallowed"),
    ("test.1", "notallowed/.."),
    ("/test.1",),
    ("../test.1",),
], _BlobDBTests)
def test_bad_name(self, name, bucket=mod.DEFAULT_BUCKET):
    with self.assertRaises(mod.BadName):
        self.db.get(name, bucket)


class TestFilesystemBlobDB(TestCase, _BlobDBTests):

    @classmethod
    def setUpClass(cls):
        cls.rootdir = mkdtemp(prefix="blobdb")
        cls.db = mod.FilesystemBlobDB(cls.rootdir)

    @classmethod
    def tearDownClass(cls):
        cls.db = None
        rmtree(cls.rootdir)
        cls.rootdir = None

    def test_put_with_colliding_blob_id(self):
        # unfortunately can't do this on S3 because there is no way to
        # reliably check if an object exists before putting it.
        ident = get_id()
        self.db.put(StringIO(b"bing"), ident)
        with self.assertRaises(mod.FileExists):
            self.db.put(StringIO(b"bang"), ident)

    def test_delete(self):
        info, bucket = super(TestFilesystemBlobDB, self).test_delete()
        self.assertFalse(self.db.delete(info.identifier, bucket), 'delete should fail')

    def test_bulk_delete(self):
        paths = super(TestFilesystemBlobDB, self).test_bulk_delete()
        self.assertFalse(self.db.bulk_delete(paths), 'delete should fail')

    def test_delete_bucket(self):
        super(TestFilesystemBlobDB, self).test_delete_bucket()
        names = os.listdir(self.db.get_path(bucket="doctype"))
        self.assertNotIn("ys7v136b", names, "bucket not deleted")

    def test_bucket_path(self):
        bucket = join("doctype", "8cd98f0")
        self.db.put(StringIO(b"content"), get_id(), bucket=bucket)
        path = self.db.get_path(bucket=bucket)
        self.assertTrue(isdir(path), path)
        self.assertTrue(os.listdir(path))

    def test_empty_attachment_name(self):
        info = super(TestFilesystemBlobDB, self).test_empty_attachment_name()
        path = self.db.get_path(info.identifier)
        with open(path, "rb") as fh:
            self.assertEqual(fh.read(), b"content")


@generate_cases([
    ((1, 2), {}, 1, 2),
    ((1,), {"bucket": 2}, 1, 2),
    ((1,), {}, 1, mod.DEFAULT_BUCKET),
    ((), {"identifier": 1}, 1, mod.DEFAULT_BUCKET),
    ((), {"identifier": 1, "bucket": 2}, 1, 2),
    ((), {"bucket": 2}, None, 2),
    ((), {"bucket": mod.DEFAULT_BUCKET}, None, mod.DEFAULT_BUCKET),
    ((), {}, ArgumentError),
    ((None,), {}, ArgumentError),
    ((None, 2), {}, ArgumentError),
    ((), {"identifier": None}, ArgumentError),
], TestFilesystemBlobDB)
def test_get_args_for_delete(self, args, kw, identifier, bucket=None):
    if isinstance(identifier, type):
        with self.assertRaises(identifier):
            self.db.get_args_for_delete(*args, **kw)
    else:
        ident, buck = self.db.get_args_for_delete(*args, **kw)
        self.assertEqual(ident, identifier)
        self.assertEqual(buck, bucket)
