from __future__ import absolute_import
from __future__ import unicode_literals
from abc import abstractmethod
from django.test import SimpleTestCase
from fakecouch import FakeCouchDb
from pillowtop.dao.couch import CouchDocumentStore
from pillowtop.dao.exceptions import DocumentNotFoundError
from pillowtop.dao.mock import MockDocumentStore


class _AbstractDocumentStoreTestCase(SimpleTestCase):

    @property
    @abstractmethod
    def dao(self):
        pass

    def test_get_missing(self):
        with self.assertRaises(DocumentNotFoundError):
            self.dao.get_document('missing-doc')

    def test_save_and_get(self):
        dao = self.dao
        id = 'test-id'
        dao.save_document(id, {'hello': 'world'})
        document = dao.get_document(id)
        self.assertEqual('world', document['hello'])

    def test_save_and_delete(self):
        dao = self.dao
        id = 'test-id-to-delete'
        dao.save_document(id, {'foo': 'bar'})
        dao.delete_document(id)
        with self.assertRaises(DocumentNotFoundError):
            self.dao.get_document(id)

    def test_delete_missing(self):
        with self.assertRaises(DocumentNotFoundError):
            self.dao.delete_document('missing-id')


class MockDocumentStoreTestCase(_AbstractDocumentStoreTestCase):

    @property
    def dao(self):
        return MockDocumentStore()


class CouchDbDocumentStoreTestCase(_AbstractDocumentStoreTestCase):

    @property
    def dao(self):
        return CouchDocumentStore(FakeCouchDb())
