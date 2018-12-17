from __future__ import unicode_literals
from __future__ import absolute_import
from datetime import datetime, timedelta
from io import BytesIO

from django.test import TestCase

from corehq.blobs.models import BlobMeta
from corehq.blobs.tests.util import new_meta, TemporaryFilesystemBlobDB
from corehq.util.test_utils import generate_cases


class TestBlobMeta(TestCase):

    @classmethod
    def setUpClass(cls):
        super(TestBlobMeta, cls).setUpClass()
        cls.db = TemporaryFilesystemBlobDB()

    @classmethod
    def tearDownClass(cls):
        cls.db.close()
        super(TestBlobMeta, cls).tearDownClass()

    def test_open(self):
        meta = self.db.put(BytesIO(b"content"), meta=new_meta())
        with meta.open() as fh:
            self.assertEqual(fh.read(), b"content")

    def test_delete_permanent_metadata(self):
        meta = self.db.put(BytesIO(b"content"), meta=new_meta())
        self.db.delete(key=meta.key)
        deleted = BlobMeta.objects.get(id=meta.id)
        self.assertFalse(deleted.deleted_on is None)
        self.assertLessEqual(deleted.deleted_on, datetime.utcnow())

    def test_bulk_delete_permanent_metadata(self):
        meta = self.db.put(BytesIO(b"content"), meta=new_meta())
        self.db.delete(key=meta.key)
        deleted = BlobMeta.objects.get(id=meta.id)
        self.assertFalse(deleted.deleted_on is None)
        self.assertLessEqual(deleted.deleted_on, datetime.utcnow())

    def test_delete_temporary_metadata(self):
        exp = datetime.utcnow() + timedelta(seconds=30)
        meta = self.db.put(BytesIO(b"content"), meta=new_meta(expires_on=exp))
        self.db.delete(key=meta.key)
        with self.assertRaises(BlobMeta.DoesNotExist):
            BlobMeta.objects.get(id=meta.id)

    def test_bulk_delete_temporary_metadata(self):
        exp = datetime.utcnow() + timedelta(seconds=30)
        meta = self.db.put(BytesIO(b"content"), meta=new_meta(expires_on=exp))
        self.db.bulk_delete(metas=[meta])
        with self.assertRaises(BlobMeta.DoesNotExist):
            BlobMeta.objects.get(id=meta.id)


@generate_cases([
    ("image/gif", True),
    ("image/jpeg", True),
    ("image/png", True),
    ("text/plain", False),
    ("application/octet-stream", False),
], TestBlobMeta)
def test_is_image(self, content_type, result):
    meta = new_meta(content_type=content_type)
    self.assertEqual(meta.is_image, result)
