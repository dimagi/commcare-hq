import gzip
import os
from datetime import datetime, timedelta
from io import BytesIO, open
from os.path import isdir, join
from shutil import rmtree
from tempfile import mkdtemp

from django.test import TestCase
from mock import patch

import corehq.blobs.fsdb as mod
from corehq.blobs import CODES
from corehq.blobs.metadata import MetaDB
from corehq.blobs.tasks import delete_expired_blobs
from corehq.blobs.tests.util import new_meta, temporary_blob_db
from corehq.util.metrics.tests.utils import capture_metrics
from corehq.util.test_utils import generate_cases


class _BlobDBTests(object):
    meta_kwargs = {}

    def new_meta(self, **kwargs):
        kwargs.update(self.meta_kwargs)
        return new_meta(**kwargs)

    def test_has_metadb(self):
        self.assertIsInstance(self.db.metadb, MetaDB)

    def test_put_and_get(self):
        identifier = self.new_meta()
        meta = self.db.put(BytesIO(b"content"), meta=identifier)
        self.assertEqual(identifier, meta)
        with self.db.get(meta=meta) as fh:
            self.assertEqual(fh.read(), b"content")

    def test_put_and_size(self):
        identifier = self.new_meta()
        with capture_metrics() as metrics:
            meta = self.db.put(BytesIO(b"content"), meta=identifier)
        size = meta.stored_content_length

        self.assertEqual(metrics.sum('commcare.blobs.added.count', type='tempfile'), 1)
        self.assertEqual(metrics.sum('commcare.blobs.added.bytes', type='tempfile'), size)
        self.assertEqual(self.db.size(key=meta.key), size)

    def test_put_with_timeout(self):
        meta = self.db.put(
            BytesIO(b"content"),
            domain="test",
            parent_id="test",
            type_code=CODES.tempfile,
            timeout=60,
        )
        with self.db.get(meta=meta) as fh:
            self.assertEqual(fh.read(), b"content")
        self.assertLessEqual(
            meta.expires_on - datetime.utcnow(),
            timedelta(minutes=60),
        )

    def test_put_and_get_with_unicode(self):
        identifier = self.new_meta(name='Łukasz')
        meta = self.db.put(BytesIO(b'\xc5\x81ukasz'), meta=identifier)
        self.assertEqual(identifier, meta)
        with self.db.get(meta=meta) as fh:
            self.assertEqual(fh.read(), b'\xc5\x81ukasz')

    def test_put_from_get_stream(self):
        old = self.db.put(BytesIO(b"content"), meta=self.new_meta())
        with self.db.get(meta=old) as fh:
            new = self.db.put(fh, meta=self.new_meta())
        with self.db.get(meta=new) as fh:
            self.assertEqual(fh.read(), b"content")

    def test_exists(self):
        meta = self.db.put(BytesIO(b"content"), meta=self.new_meta())
        self.assertTrue(self.db.exists(key=meta.key), 'not found')

    def test_delete_not_exists(self):
        meta = self.db.put(BytesIO(b"content"), meta=self.new_meta())
        self.db.delete(key=meta.key)
        self.assertFalse(self.db.exists(key=meta.key), 'not deleted')

    def test_delete(self):
        meta = self.db.put(BytesIO(b"content"), meta=self.new_meta())
        self.assertTrue(self.db.delete(key=meta.key), 'delete failed')
        with self.assertRaises(mod.NotFound):
            self.db.get(meta=meta)
        return meta

    def test_bulk_delete(self):
        metas = [
            self.db.put(BytesIO("content-{}".format(key).encode('utf-8')), meta=self.new_meta())
            for key in ['test.5', 'test.6']
        ]

        with capture_metrics() as metrics:
            self.assertTrue(self.db.bulk_delete(metas=metas), 'delete failed')
        size = sum(meta.stored_content_length for meta in metas)
        self.assertEqual(metrics.sum("commcare.blobs.deleted.count"), 2)
        self.assertEqual(metrics.sum("commcare.blobs.deleted.bytes"), size)

        for meta in metas:
            with self.assertRaises(mod.NotFound):
                self.db.get(meta=meta)

        return metas

    def test_delete_no_args(self):
        meta = self.db.put(BytesIO(b"content"), meta=self.new_meta())
        with self.assertRaises(TypeError):
            self.db.delete()
        with self.db.get(meta=meta) as fh:
            self.assertEqual(fh.read(), b"content")
        self.assertTrue(self.db.delete(key=meta.key))

    def test_empty_attachment_name(self):
        meta = self.db.put(BytesIO(b"content"), meta=self.new_meta())
        self.assertNotIn(".", meta.key)
        return meta

    def test_put_with_colliding_blob_id(self):
        meta = self.new_meta()
        self.db.put(BytesIO(b"bing"), meta=meta)
        self.db.put(BytesIO(b"bang"), meta=meta)
        with self.db.get(meta=meta) as fh:
            self.assertEqual(fh.read(), b"bang")

    def test_expire(self):
        now = datetime.utcnow()
        meta = self.db.put(
            BytesIO(b"content"),
            domain="test",
            parent_id="test",
            type_code=CODES.tempfile,
        )
        with self.db.get(meta=meta) as fh:
            self.assertEqual(fh.read(), b"content")
        self.db.expire("test", meta.key)

        future_date = now + timedelta(minutes=120)
        with temporary_blob_db(self.db), \
                patch('corehq.blobs.tasks._utcnow', return_value=future_date):
            delete_expired_blobs()

        with self.assertRaises(mod.NotFound):
            self.db.get(meta=meta)

    def test_expire_missing_blob(self):
        self.db.expire("test", "abc")  # should not raise error
        with self.assertRaises(mod.NotFound):
            self.db.get(key="abc", type_code=CODES.tempfile)


@generate_cases([
    ("\u4500.1/test.1",),
    ("/tmp/notallowed/test.1",),
    ("./test.1",),
    ("../test.1",),
    ("../notallowed/test.1",),
    ("notallowed/../test.1",),
    ("/test.1",),
], _BlobDBTests)
def test_bad_name(self, key):
    with self.assertRaises(mod.BadName):
        self.db.get(key=key, type_code=CODES.tempfile)


class TestFilesystemBlobDB(TestCase, _BlobDBTests):

    @classmethod
    def setUpClass(cls):
        super(TestFilesystemBlobDB, cls).setUpClass()
        cls.rootdir = mkdtemp(prefix="blobdb")
        cls.db = mod.FilesystemBlobDB(cls.rootdir)

    @classmethod
    def tearDownClass(cls):
        cls.db = None
        rmtree(cls.rootdir)
        cls.rootdir = None
        super(TestFilesystemBlobDB, cls).tearDownClass()

    def test_delete(self):
        meta = super(TestFilesystemBlobDB, self).test_delete()
        self.assertFalse(self.db.delete(key=meta.key), 'delete should fail')

    def test_bulk_delete(self):
        metas = super(TestFilesystemBlobDB, self).test_bulk_delete()
        self.assertFalse(self.db.bulk_delete(metas=metas), 'delete should fail')

    def test_blob_path(self):
        meta = new_meta(key=join("doctype", "8cd98f0", "blob_id"))
        self.db.put(BytesIO(b"content"), meta=meta)
        path = os.path.dirname(self.db.get_path(key=meta.key))
        self.assertTrue(isdir(path), path)
        self.assertTrue(os.listdir(path))

    def test_empty_attachment_name(self):
        meta = super(TestFilesystemBlobDB, self).test_empty_attachment_name()
        path = self.db.get_path(key=meta.key)
        self._check_file_content(path, b"content")

    def _check_file_content(self, path, expected):
        with open(path, "rb") as fh:
            self.assertEqual(fh.read(), expected)


class TestFilesystemBlobDBCompressed(TestFilesystemBlobDB):
    meta_kwargs = {'compressed_length': -1}

    def _check_file_content(self, path, expected):
        with gzip.open(path, 'rb') as fh:
            self.assertEqual(fh.read(), expected)
