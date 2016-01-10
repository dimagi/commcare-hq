from pillowtop.dao.exceptions import DocumentNotFoundError
from pillowtop.dao.interface import DocumentStore


class MockDocumentStore(DocumentStore):

    def __init__(self):
        self._data_store = {}

    def get_document(self, doc_id):
        try:
            return self._data_store[doc_id]
        except KeyError:
            raise DocumentNotFoundError()

    def save_document(self, doc_id, document):
        self._data_store[doc_id] = document

    def delete_document(self, doc_id):
        try:
            del self._data_store[doc_id]
        except KeyError:
            raise DocumentNotFoundError()
