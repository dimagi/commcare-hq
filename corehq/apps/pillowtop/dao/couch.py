import six
from couchdbkit import ResourceNotFound
from dimagi.utils.couch.database import iter_docs
from .interface import DocumentStore
from pillowtop.dao.exceptions import DocumentMissingError, DocumentDeletedError, DocumentNotFoundError


ID_CHUNK_SIZE = 10000


class CouchDocumentStore(DocumentStore):

    def __init__(self, couch_db, domain=None, doc_type=None):
        self._couch_db = couch_db
        self.domain = domain
        self.doc_type = doc_type

    def get_document(self, doc_id):
        try:
            return self._couch_db.get(doc_id)
        except ResourceNotFound as e:
            if six.text_type(e) == 'missing':
                raise DocumentMissingError()
            else:
                raise DocumentDeletedError()

    def iter_document_ids(self):
        from corehq.apps.domain.dbaccessors import iterate_doc_ids_in_domain_by_type

        if not (self.domain and self.doc_type):
            raise ValueError('This function requires a domain and doc_type set!')

        return iterate_doc_ids_in_domain_by_type(
            self.domain,
            self.doc_type,
            chunk_size=ID_CHUNK_SIZE,
            database=self._couch_db,
        )

    def iter_documents(self, ids):
        return iter_docs(self._couch_db, ids, chunksize=500)


_DATE_MAP = {
    'XFormInstance': 'received_on',
    'CommCareCase': 'opened_on',
}
