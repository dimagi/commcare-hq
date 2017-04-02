from unittest import TestCase
from StringIO import StringIO

from corehq.blobs.atomic import AtomicBlobs
from corehq.blobs.exceptions import InvalidContext, NotFound
from corehq.blobs.tests.util import TemporaryFilesystemBlobDB, get_id


class TestFilesystemBlobDB(TestCase):

    @classmethod
    def setUpClass(cls):
        cls.db = TemporaryFilesystemBlobDB()

    @classmethod
    def tearDownClass(cls):
        cls.db.close()

    def test_put(self):
        with AtomicBlobs(self.db) as db:
            info = db.put(StringIO(b"content"), get_id())
        with self.db.get(info.identifier) as fh:
            self.assertEqual(fh.read(), b"content")

    def test_put_failed(self):
        with self.assertRaises(Boom), AtomicBlobs(self.db) as db:
            info = db.put(StringIO(b"content"), get_id())
            raise Boom()
        with self.assertRaises(NotFound):
            self.db.get(info.identifier)

    def test_put_outside_context(self):
        with AtomicBlobs(self.db) as db:
            pass
        with self.assertRaises(InvalidContext):
            db.put(StringIO(b"content"), get_id())

    def test_delete(self):
        info = self.db.put(StringIO(b"content"), get_id())
        with AtomicBlobs(self.db) as db:
            db.delete(info.identifier)
        with self.assertRaises(NotFound):
            self.db.get(info.identifier)

    def test_delete_failed(self):
        info = self.db.put(StringIO(b"content"), get_id())
        with self.assertRaises(Boom), AtomicBlobs(self.db) as db:
            db.delete(info.identifier)
            raise Boom()
        with self.db.get(info.identifier) as fh:
            self.assertEqual(fh.read(), b"content")

    def test_delete_outside_context(self):
        with AtomicBlobs(self.db) as db:
            pass
        with self.assertRaises(InvalidContext):
            db.delete(StringIO(b"content"))


class Boom(Exception):
    pass
