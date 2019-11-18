from django.conf import settings

from casexml.apps.phone.document_store import SyncLogDocumentStore
from couchforms.models import all_known_formlike_doc_types
from pillowtop.dao.couch import CouchDocumentStore

from corehq.apps.change_feed import topics
from corehq.apps.change_feed.exceptions import UnknownDocumentStore
from corehq.apps.locations.document_store import (
    LOCATION_DOC_TYPE,
    LocationDocumentStore,
)
from corehq.apps.sms.document_stores import SMSDocumentStore
from corehq.form_processor.document_stores import (
    DocStoreLoadTracker,
    LedgerV1DocumentStore,
    CaseDocumentStore,
    FormDocumentStore,
    LedgerV2DocumentStore,
)
from corehq.util.couch import get_db_by_doc_type
from corehq.util.couchdb_management import couch_config
from corehq.util.datadog.utils import (
    case_load_counter,
    form_load_counter,
    ledger_load_counter,
    sms_load_counter,
)
from corehq.util.exceptions import DatabaseNotFound

SOURCE_COUCH = 'couch'
SOURCE_SQL = 'sql'

FORM_SQL = 'form-sql'
CASE_SQL = 'case-sql'
SMS = 'sms'
LEDGER_V2 = 'ledger-v2'
LEDGER_V1 = 'ledger-v1'
LOCATION = 'location'
SYNCLOG_SQL = 'synclog-sql'


def get_document_store(data_source_type, data_source_name, domain, load_source="unknown"):
    # change this to just 'data_source_name' after June 2018
    type_or_name = (data_source_type, data_source_name)
    if data_source_type == SOURCE_COUCH:
        try:
            return CouchDocumentStore(couch_config.get_db_for_db_name(data_source_name))
        except DatabaseNotFound:
            # in debug mode we may be flipping around our databases so don't fail hard here
            if settings.DEBUG:
                return None
            raise
    elif FORM_SQL in type_or_name:
        store = FormDocumentStore(domain)
        load_counter = form_load_counter
    elif CASE_SQL in type_or_name:
        store = CaseDocumentStore(domain)
        load_counter = case_load_counter
    elif SMS in type_or_name:
        store = SMSDocumentStore()
        load_counter = sms_load_counter
    elif LEDGER_V2 in type_or_name:
        store = LedgerV2DocumentStore(domain)
        load_counter = ledger_load_counter
    elif LEDGER_V1 in type_or_name:
        store = LedgerV1DocumentStore(domain)
        load_counter = ledger_load_counter
    elif LOCATION in type_or_name:
        return LocationDocumentStore(domain)
    elif SYNCLOG_SQL in type_or_name:
        return SyncLogDocumentStore()
    else:
        raise UnknownDocumentStore(
            'getting document stores for backend {} is not supported!'.format(data_source_type)
        )
    track_load = load_counter(load_source, domain)
    return DocStoreLoadTracker(store, track_load)


def get_document_store_for_doc_type(domain, doc_type, case_type_or_xmlns=None, load_source="unknown"):
    """Only applies to documents that have a document type:
    * forms
    * cases
    * locations
    * leddgers (V2 only)
    * all couch models
    """
    from corehq.apps.change_feed import document_types
    if doc_type in all_known_formlike_doc_types():
        store = FormDocumentStore(domain, xmlns=case_type_or_xmlns)
        load_counter = form_load_counter
    elif doc_type in document_types.CASE_DOC_TYPES:
        store = CaseDocumentStore(domain, case_type=case_type_or_xmlns)
        load_counter = case_load_counter
    elif doc_type == LOCATION_DOC_TYPE:
        return LocationDocumentStore(domain)
    elif doc_type == topics.LEDGER:
        return LedgerV2DocumentStore(domain)
    else:
        # all other types still live in couchdb
        return CouchDocumentStore(
            couch_db=get_db_by_doc_type(doc_type),
            domain=domain,
            doc_type=doc_type
        )
    track_load = load_counter(load_source, domain)
    return DocStoreLoadTracker(store, track_load)
