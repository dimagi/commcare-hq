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

    def iter_documents(self, ids):
        for doc_id in ids:
            yield self.get_document(doc_id)

    def iter_document_ids(self, last_id=None):
        return iter(self._data_store)
