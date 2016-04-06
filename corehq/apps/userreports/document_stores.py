from casexml.apps.case.models import CommCareCase
from corehq.form_processor.document_stores import ReadonlyFormDocumentStore, ReadonlyCaseDocumentStore
from corehq.form_processor.utils import should_use_sql_backend
from couchforms.models import XFormInstance
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
            couch_db=_get_db(doc_type),
            domain=domain,
            doc_type=doc_type
        )


def _get_db(doc_type):
    return _DOC_TYPE_MAPPING.get(doc_type, CommCareCase).get_db()


# This is intentionally not using magic to introspect the class from the name, though it could
from corehq.apps.locations.models import Location
_DOC_TYPE_MAPPING = {
    'XFormInstance': XFormInstance,
    'CommCareCase': CommCareCase,
    'Location': Location
}
