import doctest

from django.test import SimpleTestCase

from dimagi.ext.couchdbkit import Document
from dimagi.utils.couch.undo import (
    get_deleted_doc_type,
    soft_delete,
    undo_delete,
)


class TestDocument(Document):
    saved = False

    def save(self):
        self.saved = True


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


class TestUndoDelete(SimpleTestCase):

    def test_undo_delete(self):
        document = TestDocument(doc_type='Completed')
        soft_delete(document)
        self.assertEqual(document.doc_type, 'Completed-Deleted')
        undo_delete(document)
        self.assertEqual(document.doc_type, 'Completed')

    def test_undo_delete_dont_save(self):
        document = TestDocument(doc_type='Completed-Deleted')
        undo_delete(document, save=False)
        self.assertFalse(document.saved)

    def test_undo_delete_saves_unchanged(self):
        document = TestDocument(doc_type='Completed')
        undo_delete(document)
        self.assertEqual(document.doc_type, 'Completed')
        self.assertTrue(document.saved)


def test_doctests():
    import dimagi.utils.couch.undo

    results = doctest.testmod(dimagi.utils.couch.undo)
    assert results.failed == 0
