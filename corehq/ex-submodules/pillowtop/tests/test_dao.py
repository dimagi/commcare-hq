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

    @abstractmethod
    def save(self, dao, doc_id, doc):
        pass

    def test_get_missing(self):
        with self.assertRaises(DocumentNotFoundError):
            self.dao.get_document('missing-doc')

    def test_save_and_get(self):
        dao = self.dao
        id = 'test-id'
        self.save(dao, id, {'hello': 'world'})
        document = dao.get_document(id)
        self.assertEqual('world', document['hello'])


class MockDocumentStoreTestCase(_AbstractDocumentStoreTestCase):

    @property
    def dao(self):
        return MockDocumentStore()

    def save(self, dao, doc_id, doc):
        dao._data_store[doc_id] = doc


class CouchDbDocumentStoreTestCase(_AbstractDocumentStoreTestCase):

    @property
    def dao(self):
        return CouchDocumentStore(FakeCouchDb())

    def save(self, dao, doc_id, doc):
        doc['_id'] = doc_id
        dao._couch_db.save_doc(doc)
