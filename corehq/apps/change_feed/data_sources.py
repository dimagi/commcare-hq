from __future__ import absolute_import
from __future__ import unicode_literals
from django.conf import settings
from casexml.apps.phone.document_store import ReadonlySyncLogDocumentStore
from corehq.apps.change_feed import topics
from corehq.apps.change_feed.exceptions import UnknownDocumentStore, UnknownChangeVersion
from corehq.apps.locations.document_store import ReadonlyLocationDocumentStore
from corehq.apps.sms.document_stores import ReadonlySMSDocumentStore
from corehq.form_processor.document_stores import (
    ReadonlyFormDocumentStore, ReadonlyCaseDocumentStore, ReadonlyLedgerV2DocumentStore,
    LedgerV1DocumentStore
)
from corehq.util.couchdb_management import couch_config
from corehq.util.exceptions import DatabaseNotFound
from couchforms.models import all_known_formlike_doc_types
from pillowtop.dao.couch import CouchDocumentStore

COUCH = 'couch'
FORM_SQL = 'form-sql'
CASE_SQL = 'case-sql'
SMS = 'sms'
LEDGER_V2 = 'ledger-v2'
LEDGER_V1 = 'ledger-v1'
LOCATION = 'location'
SYNCLOG_SQL = 'synclog-sql'


def get_document_store_for_change_meta(change_meta):
    if change_meta.version == 1:
        return _get_document_store_from_doc_type(
            change_meta.document_type, change_meta.domain, change_meta.backend_id
        )

    if change_meta.version == 0:
        return _get_document_store_v0(
            data_source_type=change_meta.data_source_type,
            data_source_name=change_meta.data_source_name,
            domain=change_meta.domain
        )

    raise UnknownChangeVersion(change_meta.version)


def _get_document_store_v0(data_source_type, data_source_name, domain):
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


def _get_document_store_from_doc_type(doc_type, domain, backend_id=None):
    if not backend_id or backend_id == 'couch':
        doc_type = doc_type.split('-')[0]  # trip suffixes like '-DELETED'
        couch_db = couch_config.get_db_for_doc_type(doc_type)
        return CouchDocumentStore(couch_db, domain)
    else:
        from corehq.apps.change_feed import document_types
        if doc_type in all_known_formlike_doc_types():
            return ReadonlyFormDocumentStore(domain)
        elif doc_type in document_types.CASE_DOC_TYPES:
            return ReadonlyCaseDocumentStore(domain)

        # for docs that don't have a doc_type we use the Kafka topic
        elif doc_type == topics.SMS:
            return ReadonlySMSDocumentStore()
        elif doc_type == topics.LEDGER_V2:
            return ReadonlyLedgerV2DocumentStore(domain)
        elif doc_type == topics.LEDGER:
            return LedgerV1DocumentStore(domain)
        elif doc_type == topics.LOCATION:
            return ReadonlyLocationDocumentStore(domain)
        elif doc_type in document_types.SYNCLOG_DOC_TYPES or doc_type == topics.SYNCLOG_SQL:
            return ReadonlySyncLogDocumentStore()
        else:
            raise UnknownDocumentStore(
                'getting document stores for backend {} is not supported!'.format(doc_type)
            )
