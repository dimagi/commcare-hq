from couchdbkit import ResourceNotFound
from .interface import DocumentStore
from pillowtop.dao.exceptions import DocumentNotFoundError


class CouchDocumentStore(DocumentStore):

    def __init__(self, couch_db):
        self._couch_db = couch_db

    def get_document(self, doc_id):
        try:
            return self._couch_db.get(doc_id)
        except ResourceNotFound:
            raise DocumentNotFoundError()

    def save_document(self, doc_id, document):
        document['_id'] = doc_id
        self._couch_db.save_doc(document)

    def delete_document(self, doc_id):
        try:
            return self._couch_db.delete_doc(doc_id)
        except ResourceNotFound:
            raise DocumentNotFoundError()
