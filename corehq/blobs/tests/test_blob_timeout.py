from __future__ import absolute_import
from __future__ import unicode_literals
from io import StringIO
from mock import patch
from datetime import datetime, timedelta
from django.test import TestCase

from corehq.blobs.exceptions import NotFound
from corehq.blobs.tasks import delete_expired_blobs
from corehq.blobs.tests.util import TemporaryFilesystemBlobDB
from corehq.blobs.models import BlobExpiration


class BlobExpireTest(TestCase):

    identifier = 'blob-identifier'
    bucket = 'blob-bucket'

    @classmethod
    def setUpClass(cls):
        super(BlobExpireTest, cls).setUpClass()
        cls.db = TemporaryFilesystemBlobDB()

    @classmethod
    def tearDownClass(cls):
        cls.db.close()
        super(BlobExpireTest, cls).tearDownClass()

    def tearDown(self):
        BlobExpiration.objects.all().delete()
        if self.db.exists(self.identifier, self.bucket):
            self.db.delete(self.identifier, self.bucket)

    def test_blob_expires(self):
        now = datetime(2017, 1, 1)

        with patch('corehq.blobs.util._utcnow', return_value=now):
            self.db.put(StringIO('content'), self.identifier, bucket=self.bucket, timeout=60)

        self.assertIsNotNone(self.db.get(self.identifier, self.bucket))
        with patch('corehq.blobs.tasks._utcnow', return_value=now + timedelta(minutes=61)):
            bytes_deleted = delete_expired_blobs()

        self.assertEqual(bytes_deleted, len('content'))

        with self.assertRaises(NotFound):
            self.db.get(self.identifier, self.bucket)

        self.assertEqual(BlobExpiration.objects.all().count(), 1)

    def test_blob_does_not_expire(self):
        now = datetime(2017, 1, 1)

        with patch('corehq.blobs.util._utcnow', return_value=now):
            self.db.put(StringIO('content'), self.identifier, bucket=self.bucket, timeout=60)

        self.assertIsNotNone(self.db.get(self.identifier, self.bucket))
        with patch('corehq.blobs.tasks._utcnow', return_value=now + timedelta(minutes=30)):
            delete_expired_blobs()

        self.assertIsNotNone(self.db.get(self.identifier, self.bucket))
        self.assertEqual(BlobExpiration.objects.all().count(), 1)

    def test_duplicate_identifier_expire(self):
        now = datetime(2017, 1, 1)

        with patch('corehq.blobs.util._utcnow', return_value=now):
            self.db.put(StringIO('content'), self.identifier, bucket=self.bucket, timeout=60)

        self.assertIsNotNone(self.db.get(self.identifier, self.bucket))
        with patch('corehq.blobs.tasks._utcnow', return_value=now + timedelta(minutes=61)):
            delete_expired_blobs()

        with self.assertRaises(NotFound):
            self.db.get(self.identifier, self.bucket)

        now = datetime(2018, 1, 1)
        # Put another blob a year later with the same identifier
        with patch('corehq.blobs.util._utcnow', return_value=now):
            self.db.put(StringIO('content'), self.identifier, bucket=self.bucket, timeout=60)

        # Even though there is an old BlobExpiration record for that bucket/identifier,
        # we should not delete delete the new blob
        with patch('corehq.blobs.tasks._utcnow', return_value=now + timedelta(minutes=0)):
            delete_expired_blobs()

        self.assertIsNotNone(self.db.get(self.identifier, self.bucket))
        self.assertEqual(BlobExpiration.objects.all().count(), 2)
