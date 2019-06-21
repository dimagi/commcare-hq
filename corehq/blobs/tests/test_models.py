from __future__ import unicode_literals
from __future__ import absolute_import
from datetime import datetime, timedelta
from io import BytesIO

from django.test import TestCase
from mock import patch

from corehq.blobs.models import BlobMeta, DeletedBlobMeta
from corehq.blobs.tests.util import get_meta, new_meta, TemporaryFilesystemBlobDB
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
        early = datetime.utcnow() - timedelta(minutes=5)
        meta = self.db.put(BytesIO(b"content"), meta=new_meta(created_on=early))
        self.db.delete(key=meta.key)
        with self.assertRaises(BlobMeta.DoesNotExist):
            get_meta(meta)
        deleted = get_meta(meta, deleted=True)
        self.assertFalse(deleted.deleted_on is None)
        self.assertGreaterEqual(deleted.deleted_on, meta.created_on)
        self.assertLessEqual(deleted.deleted_on, datetime.utcnow())

    def test_bulk_delete_permanent_metadata(self):
        meta = self.db.put(BytesIO(b"content"), meta=new_meta())
        now = datetime.utcnow()
        with patch('corehq.blobs.metadata._utcnow', return_value=now):
            self.db.bulk_delete(metas=[meta])
            with self.assertRaises(BlobMeta.DoesNotExist):
                get_meta(meta)
            deleted = get_meta(meta, deleted=True)
            self.assertEqual(deleted.deleted_on, now)

    def test_delete_temporary_metadata(self):
        exp = datetime.utcnow() + timedelta(seconds=30)
        meta = self.db.put(BytesIO(b"content"), meta=new_meta(expires_on=exp))
        self.db.delete(key=meta.key)
        with self.assertRaises(BlobMeta.DoesNotExist):
            get_meta(meta)
        with self.assertRaises(DeletedBlobMeta.DoesNotExist):
            get_meta(meta, deleted=True)

    def test_bulk_delete_temporary_metadata(self):
        exp = datetime.utcnow() + timedelta(seconds=30)
        meta = self.db.put(BytesIO(b"content"), meta=new_meta(expires_on=exp))
        self.db.bulk_delete(metas=[meta])
        with self.assertRaises(BlobMeta.DoesNotExist):
            get_meta(meta)
        with self.assertRaises(DeletedBlobMeta.DoesNotExist):
            get_meta(meta, deleted=True)


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
