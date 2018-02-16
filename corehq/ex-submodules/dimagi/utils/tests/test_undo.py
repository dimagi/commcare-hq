from __future__ import absolute_import
from django.test import SimpleTestCase
from dimagi.ext.couchdbkit import Document
from dimagi.utils.couch.undo import get_deleted_doc_type


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
