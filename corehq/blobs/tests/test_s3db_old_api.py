"""Test S3 Blob DB"""
from __future__ import unicode_literals
from __future__ import absolute_import
from os.path import join
from io import BytesIO

from django.conf import settings
from django.test import TestCase

from corehq.blobs.tests.util import get_id, TemporaryS3BlobDB
from corehq.blobs.tests.test_fsdb_old_api import _BlobDBTests
from corehq.util.test_utils import trap_extra_setup


class TestS3BlobDB(TestCase, _BlobDBTests):

    @classmethod
    def setUpClass(cls):
        super(TestS3BlobDB, cls).setUpClass()
        with trap_extra_setup(AttributeError, msg="S3_BLOB_DB_SETTINGS not configured"):
            config = settings.S3_BLOB_DB_SETTINGS
        cls.db = TemporaryS3BlobDB(config)

    @classmethod
    def tearDownClass(cls):
        cls.db.close()
        super(TestS3BlobDB, cls).tearDownClass()

    def test_bucket_path(self):
        bucket = join("doctype", "8cd98f0")
        self.db.put(BytesIO(b"content"), get_id(), bucket=bucket)
        self.assertEqual(self.db.get_path(bucket=bucket), bucket)
