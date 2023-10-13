from datetime import datetime

from django.test import SimpleTestCase, TestCase
from dimagi.ext.couchdbkit import Document
from dimagi.utils.couch.undo import DeleteRecord, get_deleted_doc_type, undo_delete

from corehq.apps.cleanup.models import DeletedCouchDoc
from corehq.apps.groups.models import DeleteGroupRecord


class TestDocument(Document):
    pass


class TestSubDocument(TestDocument):
    pass


class TestDeletedDocType(SimpleTestCase):

    def test_format_class(self):
        self.assertEqual('TestDocument-Deleted', get_deleted_doc_type(TestDocument))

    def test_format_instance(self):
        self.assertEqual('TestDocument-Deleted', get_deleted_doc_type(TestDocument()))

    def test_format_instance_override_doc_type(self):
        self.assertEqual('FooType-Deleted', get_deleted_doc_type(TestDocument(doc_type='FooType')))

    def test_format_subclass(self):
        self.assertEqual('TestSubDocument-Deleted', get_deleted_doc_type(TestSubDocument))

    def test_format_subclass_instance(self):
        self.assertEqual('TestSubDocument-Deleted', get_deleted_doc_type(TestSubDocument()))


class TestDeleteAndUndo(TestCase):

    def test_undo_delete_removes_deleted_couch_doc_record(self):
        doc = TestDocument({
            '_id': '980023a6852643a19b87f2142b0c3ce1',
            '_rev': 'v3-980023a6852643a19b87f2142b0c3ce1',
            'doc_type': 'TestDocument-Deleted',
            'domain': 'test',
        })
        rec = DeleteGroupRecord(
            doc_id=doc["_id"],
            datetime=datetime.utcnow(),
        )
        rec.save()
        params = {'doc_id': rec._id, 'doc_type': rec.doc_type}
        assert DeletedCouchDoc.objects.get(**params)
        undo_delete(doc, delete_record=rec, save=False)
        with self.assertRaises(DeletedCouchDoc.DoesNotExist):
            DeletedCouchDoc.objects.get(**params)

    def test_delete_record_cleans_up_after_itself(self):
        rec = DeleteRecord(doc_id="980023a6852643a19b87f2142b0c3ce1")
        rec.save()
        self.addCleanup(rec.delete)
        self.assertTrue(DeletedCouchDoc.objects.filter(doc_id=rec._id, doc_type=rec.doc_type).exists())

    def test_save_delete_record_twice(self):
        rec = DeleteRecord(doc_id="980023a6852643a19b87f2142b0c3ce1")
        rec.save()
        self.addCleanup(rec.delete)
        rec.save()  # should not raise
