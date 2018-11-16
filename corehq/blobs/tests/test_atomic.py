from __future__ import absolute_import
from __future__ import unicode_literals
from django.test import TestCase
from io import BytesIO

from corehq.blobs.atomic import AtomicBlobs
from corehq.blobs.exceptions import InvalidContext, NotFound
from corehq.blobs.tests.util import TemporaryFilesystemBlobDB, new_meta


class TestAtomicBlobs(TestCase):

    @classmethod
    def setUpClass(cls):
        super(TestAtomicBlobs, cls).setUpClass()
        cls.db = TemporaryFilesystemBlobDB()

    @classmethod
    def tearDownClass(cls):
        cls.db.close()
        super(TestAtomicBlobs, cls).tearDownClass()

    def test_put(self):
        with AtomicBlobs(self.db) as db:
            meta = db.put(BytesIO(b"content"), meta=new_meta())
        with self.db.get(key=meta.key) as fh:
            self.assertEqual(fh.read(), b"content")

    def test_put_failed(self):
        with self.assertRaises(Boom), AtomicBlobs(self.db) as db:
            meta = db.put(BytesIO(b"content"), meta=new_meta())
            raise Boom()
        with self.assertRaises(NotFound):
            self.db.get(key=meta.key)

    def test_put_outside_context(self):
        with AtomicBlobs(self.db) as db:
            pass
        with self.assertRaises(InvalidContext):
            db.put(BytesIO(b"content"), meta=new_meta())

    def test_delete(self):
        meta = self.db.put(BytesIO(b"content"), meta=new_meta())
        with AtomicBlobs(self.db) as db:
            db.delete(key=meta.key)
        with self.assertRaises(NotFound):
            self.db.get(key=meta.key)

    def test_delete_failed(self):
        meta = self.db.put(BytesIO(b"content"), meta=new_meta())
        with self.assertRaises(Boom), AtomicBlobs(self.db) as db:
            db.delete(key=meta.key)
            raise Boom()
        with self.db.get(key=meta.key) as fh:
            self.assertEqual(fh.read(), b"content")

    def test_delete_outside_context(self):
        with AtomicBlobs(self.db) as db:
            pass
        with self.assertRaises(InvalidContext):
            db.delete(BytesIO(b"content"))


class Boom(Exception):
    pass
