from couchdbkit import ResourceNotFound
from dimagi.utils.couch.database import iter_docs
from .interface import DocumentStore
from pillowtop.dao.exceptions import DocumentNotFoundError


ID_CHUNK_SIZE = 10000


class CouchDocumentStore(DocumentStore):

    def __init__(self, couch_db, domain=None, doc_type=None):
        self._couch_db = couch_db
        self.domain = domain
        self.doc_type = doc_type

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

    def iter_document_ids(self, last_id=None):
        from corehq.apps.domain.dbaccessors import iterate_doc_ids_in_domain_by_type

        if not (self.domain and self.doc_type):
            raise ValueError('This function requires a domain and doc_type set!')
        start_key = None
        if last_id:
            last_doc = self.get_document(last_id)
            start_key = [self.domain, self.doc_type]
            if self.doc_type in _DATE_MAP.keys():
                start_key.append(last_doc[_DATE_MAP[self.doc_type]])

        return iterate_doc_ids_in_domain_by_type(
            self.domain,
            self.doc_type,
            chunk_size=ID_CHUNK_SIZE,
            database=self._couch_db,
            startkey=start_key,
            startkey_docid=last_id
        )

    def iter_documents(self, ids):
        return iter_docs(self._couch_db, ids, chunksize=500)


_DATE_MAP = {
    'XFormInstance': 'received_on',
    'CommCareCase': 'opened_on',
}
