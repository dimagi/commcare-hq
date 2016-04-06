from corehq.form_processor.document_stores import ReadonlyFormDocumentStore, ReadonlyCaseDocumentStore
from corehq.form_processor.utils import should_use_sql_backend
from corehq.util.couch import get_db_by_doc_type
from pillowtop.dao.couch import CouchDocumentStore


def get_document_store(domain, doc_type):
    use_sql = should_use_sql_backend(domain)
    if use_sql and doc_type == 'XFormInstance':
        return ReadonlyFormDocumentStore(domain)
    elif use_sql and doc_type == 'CommCareCase':
        return ReadonlyCaseDocumentStore(domain)
    else:
        # all other types still live in couchdb
        return CouchDocumentStore(
            couch_db=get_db_by_doc_type(doc_type),
            domain=domain,
            doc_type=doc_type
        )
