from __future__ import absolute_import
from django.conf import settings
from casexml.apps.phone.document_store import ReadonlySyncLogDocumentStore
from corehq.apps.change_feed.exceptions import UnknownDocumentStore
from corehq.apps.locations.document_store import ReadonlyLocationDocumentStore
from corehq.apps.sms.document_stores import ReadonlySMSDocumentStore
from corehq.form_processor.document_stores import (
    ReadonlyFormDocumentStore, ReadonlyCaseDocumentStore, ReadonlyLedgerV2DocumentStore,
    LedgerV1DocumentStore
)
from corehq.util.couchdb_management import couch_config
from corehq.util.exceptions import DatabaseNotFound
from pillowtop.dao.couch import CouchDocumentStore

COUCH = 'couch'
FORM_SQL = 'form-sql'
CASE_SQL = 'case-sql'
SMS = 'sms'
LEDGER_V2 = 'ledger-v2'
LEDGER_V1 = 'ledger-v1'
LOCATION = 'location'
SYNCLOG_SQL = 'synclog-sql'


def get_document_store(data_source_type, data_source_name, domain):
    if data_source_type == COUCH:
        try:
            return CouchDocumentStore(couch_config.get_db_for_db_name(data_source_name))
        except DatabaseNotFound:
            # in debug mode we may be flipping around our databases so don't fail hard here
            if settings.DEBUG:
                return None
            raise
    elif data_source_type == FORM_SQL:
        return ReadonlyFormDocumentStore(domain)
    elif data_source_type == CASE_SQL:
        return ReadonlyCaseDocumentStore(domain)
    elif data_source_type == SMS:
        return ReadonlySMSDocumentStore()
    elif data_source_type == LEDGER_V2:
        return ReadonlyLedgerV2DocumentStore(domain)
    elif data_source_type == LEDGER_V1:
        return LedgerV1DocumentStore(domain)
    elif data_source_type == LOCATION:
        return ReadonlyLocationDocumentStore(domain)
    elif data_source_type == SYNCLOG_SQL:
        return ReadonlySyncLogDocumentStore()
    else:
        raise UnknownDocumentStore(
            'getting document stores for backend {} is not supported!'.format(data_source_type)
        )
