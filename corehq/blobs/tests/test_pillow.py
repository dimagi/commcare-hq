from corehq.blobs.mixin import _get_couchdb_name
from corehq.blobs.pillow import BlobDeletionProcessor
from corehq.blobs.tests.test_mixin import BaseTestCase
from couchdbkit.exceptions import ResourceNotFound
from testil import assert_raises, Config


class TestBlobDeletionPillow(BaseTestCase):

    def setUp(self):
        super(TestBlobDeletionPillow, self).setUp()
        db_name = _get_couchdb_name(type(self.obj))
        self.processor = BlobDeletionProcessor(self.db, db_name)

    def test_process_change_with_deleted_document(self):
        self.obj.put_attachment("content", "name")
        change = Config(id=self.obj._id, deleted=True)
        self.processor.process_change(None, change, None)
        msg = "FakeCouchDocument attachment: 'name'"
        with assert_raises(ResourceNotFound, msg=msg):
            self.obj.fetch_attachment("name")

    def test_process_change_with_existing_document(self):
        self.obj.put_attachment("content", "name")
        change = Config(id=self.obj._id, deleted=False)
        self.processor.process_change(None, change, None)
        self.assertEqual(self.obj.fetch_attachment("name"), "content")
