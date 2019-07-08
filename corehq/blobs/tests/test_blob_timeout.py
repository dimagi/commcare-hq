from __future__ import absolute_import
from __future__ import unicode_literals
from io import BytesIO
from mock import patch
from datetime import datetime, timedelta
from django.test import TestCase

import corehq.blobs.tasks as mod
from corehq.blobs import CODES
from corehq.blobs.exceptions import NotFound
from corehq.blobs.tasks import delete_expired_blobs
from corehq.blobs.tests.util import TemporaryFilesystemBlobDB
from corehq.blobs.models import BlobMeta
from corehq.sql_db.util import get_db_alias_for_partitioned_doc
from corehq.util.test_utils import capture_log_output


class BlobExpireTest(TestCase):

    key = 'blob-identifier'
    args = {
        "domain": "test",
        "parent_id": "BlobExpireTest",
        "type_code": CODES.tempfile,
        "key": key,
    }

    @classmethod
    def setUpClass(cls):
        super(BlobExpireTest, cls).setUpClass()
        cls.db = TemporaryFilesystemBlobDB()

    @classmethod
    def tearDownClass(cls):
        cls.db.close()
        super(BlobExpireTest, cls).tearDownClass()

    def tearDown(self):
        if self.db.exists(key=self.key):
            self.db.delete(key=self.key)

    def test_blob_expires(self):
        now = datetime(2017, 1, 1)
        shard = get_db_alias_for_partitioned_doc(self.args["parent_id"])
        manager = BlobMeta.objects.using(shard)
        pre_expire_count = manager.count()

        with capture_log_output(mod.__name__) as logs:
            with patch('corehq.blobs.metadata._utcnow', return_value=now):
                self.db.put(BytesIO(b'content'), timeout=60, **self.args)

            self.assertIsNotNone(self.db.get(key=self.key))
            with patch('corehq.blobs.tasks._utcnow', return_value=now + timedelta(minutes=61)):
                bytes_deleted = delete_expired_blobs()

            self.assertEqual(bytes_deleted, len('content'))

            with self.assertRaises(NotFound):
                self.db.get(key=self.key)

            self.assertEqual(manager.all().count(), pre_expire_count)
            self.assertRegexpMatches(
                logs.get_output(),
                r"deleted expired blobs: .+'blob-identifier'",
            )

    def test_blob_does_not_expire(self):
        now = datetime(2017, 1, 1)
        shard = get_db_alias_for_partitioned_doc(self.args["parent_id"])
        manager = BlobMeta.objects.using(shard)
        pre_expire_count = manager.all().count()

        with patch('corehq.blobs.metadata._utcnow', return_value=now):
            self.db.put(BytesIO(b'content'), timeout=60, **self.args)

        self.assertIsNotNone(self.db.get(key=self.key))
        with patch('corehq.blobs.tasks._utcnow', return_value=now + timedelta(minutes=30)):
            delete_expired_blobs()

        self.assertIsNotNone(self.db.get(key=self.key))
        self.assertEqual(manager.all().count(), pre_expire_count + 1)
