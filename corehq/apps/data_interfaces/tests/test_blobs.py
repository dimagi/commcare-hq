from django.test import TestCase

from corehq.apps.data_interfaces.blobs import (
    read_requested_ids,
    read_skipped_ids,
    save_requested_ids,
    save_skipped_ids,
)
from corehq.blobs.tests.util import TemporaryFilesystemBlobDB


class TestBulkAsyncJobBlobs(TestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.db = TemporaryFilesystemBlobDB()

    @classmethod
    def tearDownClass(cls):
        cls.db.close()
        super().tearDownClass()

    def test_requested_ids_round_trip(self):
        key = save_requested_ids('domain', 'parent-1', ['a', 'b', 'c'])
        assert read_requested_ids(key) == ['a', 'b', 'c']

    def test_requested_ids_empty(self):
        key = save_requested_ids('domain', 'parent-1', [])
        assert read_requested_ids(key) == []

    def test_skipped_ids_round_trip(self):
        skipped = [
            {'id': 'a', 'reason': 'not_found'},
            {'id': 'b', 'reason': 'unexpected_error'},
        ]
        key = save_skipped_ids('domain', 'parent-1', skipped)
        assert read_skipped_ids(key) == skipped
