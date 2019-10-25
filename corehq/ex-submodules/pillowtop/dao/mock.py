from pillowtop.dao.exceptions import DocumentNotFoundError
from pillowtop.dao.interface import DocumentStore


class MockDocumentStore(DocumentStore):

    def __init__(self, data=None):
        self._data_store = data or {}

    def get_document(self, doc_id):
        try:
            return self._data_store[doc_id]
        except KeyError:
            raise DocumentNotFoundError()
