from __future__ import absolute_import
from __future__ import unicode_literals
from corehq.apps.locations.document_store import ReadonlyLocationDocumentStore, LOCATION_DOC_TYPE
from corehq.form_processor.document_stores import ReadonlyFormDocumentStore, ReadonlyCaseDocumentStore
from corehq.util.couch import get_db_by_doc_type
from pillowtop.dao.couch import CouchDocumentStore


def get_document_store(domain, doc_type, case_type_or_xmlns=None):
    if doc_type == 'XFormInstance':
        return ReadonlyFormDocumentStore(domain, xmlns=case_type_or_xmlns)
    elif doc_type == 'CommCareCase':
        return ReadonlyCaseDocumentStore(domain, case_type=case_type_or_xmlns)
    elif doc_type == LOCATION_DOC_TYPE:
        return ReadonlyLocationDocumentStore(domain)
    else:
        # all other types still live in couchdb
        return CouchDocumentStore(
            couch_db=get_db_by_doc_type(doc_type),
            domain=domain,
            doc_type=doc_type
        )
