# coding=utf-8
from __future__ import unicode_literals
from __future__ import absolute_import

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
from corehq.util.test_utils import generate_cases, patch_datadog


class _BlobDBTests(object):

    def test_has_metadb(self):
        self.assertIsInstance(self.db.metadb, MetaDB)

    def test_put_and_get(self):
        identifier = new_meta()
        meta = self.db.put(BytesIO(b"content"), meta=identifier)
        self.assertEqual(identifier, meta)
        with self.db.get(key=meta.key) as fh:
            self.assertEqual(fh.read(), b"content")

    def test_put_and_size(self):
        identifier = new_meta()
        with patch_datadog() as stats:
            meta = self.db.put(BytesIO(b"content"), meta=identifier)
        size = len(b'content')
        self.assertEqual(sum(s for s in stats["commcare.blobs.added.count"]), 1)
        self.assertEqual(sum(s for s in stats["commcare.blobs.added.bytes"]), size)
        self.assertEqual(self.db.size(key=meta.key), size)

    def test_put_with_timeout(self):
        meta = self.db.put(
            BytesIO(b"content"),
            domain="test",
            parent_id="test",
            type_code=CODES.tempfile,
            timeout=60,
        )
        with self.db.get(key=meta.key) as fh:
            self.assertEqual(fh.read(), b"content")
        self.assertLessEqual(
            meta.expires_on - datetime.utcnow(),
            timedelta(minutes=60),
        )

    def test_put_and_get_with_unicode(self):
        identifier = new_meta(name=u'Łukasz')
        meta = self.db.put(BytesIO(b'\xc5\x81ukasz'), meta=identifier)
        self.assertEqual(identifier, meta)
        with self.db.get(key=meta.key) as fh:
            self.assertEqual(fh.read(), b'\xc5\x81ukasz')

    def test_put_from_get_stream(self):
        old = self.db.put(BytesIO(b"content"), meta=new_meta())
        with self.db.get(key=old.key) as fh:
            new = self.db.put(fh, meta=new_meta())
        with self.db.get(key=new.key) as fh:
            self.assertEqual(fh.read(), b"content")

    def test_exists(self):
        meta = self.db.put(BytesIO(b"content"), meta=new_meta())
        self.assertTrue(self.db.exists(key=meta.key), 'not found')

    def test_delete_not_exists(self):
        meta = self.db.put(BytesIO(b"content"), meta=new_meta())
        self.db.delete(key=meta.key)
        self.assertFalse(self.db.exists(key=meta.key), 'not deleted')

    def test_delete(self):
        meta = self.db.put(BytesIO(b"content"), meta=new_meta())
        self.assertTrue(self.db.delete(key=meta.key), 'delete failed')
        with self.assertRaises(mod.NotFound):
            self.db.get(key=meta.key)
        return meta

    def test_bulk_delete(self):
        metas = [
            self.db.put(BytesIO("content-{}".format(key).encode('utf-8')), meta=new_meta())
            for key in ['test.5', 'test.6']
        ]

        with patch_datadog() as stats:
            self.assertTrue(self.db.bulk_delete(metas=metas), 'delete failed')
        self.assertEqual(sum(s for s in stats["commcare.blobs.deleted.count"]), 2)
        self.assertEqual(sum(s for s in stats["commcare.blobs.deleted.bytes"]), 28)

        for meta in metas:
            with self.assertRaises(mod.NotFound):
                self.db.get(key=meta.key)

        return metas

    def test_delete_no_args(self):
        meta = self.db.put(BytesIO(b"content"), meta=new_meta())
        with self.assertRaises(TypeError):
            self.db.delete()
        with self.db.get(key=meta.key) as fh:
            self.assertEqual(fh.read(), b"content")
        self.assertTrue(self.db.delete(key=meta.key))

    def test_empty_attachment_name(self):
        meta = self.db.put(BytesIO(b"content"), meta=new_meta())
        self.assertNotIn(".", meta.key)
        return meta

    def test_put_with_colliding_blob_id(self):
        meta = new_meta()
        self.db.put(BytesIO(b"bing"), meta=meta)
        self.db.put(BytesIO(b"bang"), meta=meta)
        with self.db.get(key=meta.key) as fh:
            self.assertEqual(fh.read(), b"bang")

    def test_expire(self):
        now = datetime.utcnow()
        meta = self.db.put(
            BytesIO(b"content"),
            domain="test",
            parent_id="test",
            type_code=CODES.tempfile,
        )
        with self.db.get(key=meta.key) as fh:
            self.assertEqual(fh.read(), b"content")
        self.db.expire("test", meta.key)

        future_date = now + timedelta(minutes=120)
        with temporary_blob_db(self.db), \
                patch('corehq.blobs.tasks._utcnow', return_value=future_date):
            delete_expired_blobs()

        with self.assertRaises(mod.NotFound):
            self.db.get(key=meta.key)

    def test_expire_missing_blob(self):
        self.db.expire("test", "abc")  # should not raise error
        with self.assertRaises(mod.NotFound):
            self.db.get(key="abc")


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
        self.db.get(key=key)


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
        with open(path, "rb") as fh:
            self.assertEqual(fh.read(), b"content")
