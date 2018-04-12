from __future__ import absolute_import
from django.conf import settings
from casexml.apps.phone.document_store import ReadonlySyncLogDocumentStore
from corehq.apps.change_feed import topics
from corehq.apps.change_feed.exceptions import UnknownDocumentStore, UnknownChangeVersion
from corehq.apps.change_feed.topics import get_topic_for_doc_type
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


def get_document_store_for_change_meta(change_meta):
    if change_meta.version == 1:
        topic = get_topic_for_doc_type(change_meta.document_type, change_meta.backend_id)
        return _get_document_store_from_topic(topic, change_meta.domain)

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


def _get_document_store_from_topic(topic, domain):
    couch_db_name = Ellipsis
    if topic in (topics.FORM, topics.CASE):
        couch_db_name = None
    elif topic == topics.APP:
        couch_db_name = settings.APPS_DB
    elif topic in (topics.WEB_USER, topics.COMMCARE_USER, topics.GROUP):
        couch_db_name = settings.USERS_GROUPS_DB
    elif topic == topics.DOMAIN:
        couch_db_name = settings.DOMAINS_DB
    elif topic == topics.META:
        couch_db_name = settings.META_DB

    if couch_db_name != Ellipsis:
        try:
            return CouchDocumentStore(couch_config.get_db_for_db_name(couch_db_name))
        except DatabaseNotFound:
            # in debug mode we may be flipping around our databases so don't fail hard here
            if settings.DEBUG:
                return None
            raise

    if topic == FORM_SQL:
        return ReadonlyFormDocumentStore(domain)
    elif topic == CASE_SQL:
        return ReadonlyCaseDocumentStore(domain)
    elif topic == SMS:
        return ReadonlySMSDocumentStore()
    elif topic == LEDGER_V2:
        return ReadonlyLedgerV2DocumentStore(domain)
    elif topic == LEDGER_V1:
        return LedgerV1DocumentStore(domain)
    elif topic == LOCATION:
        return ReadonlyLocationDocumentStore(domain)
    elif topic == SYNCLOG_SQL:
        return ReadonlySyncLogDocumentStore()
    else:
        raise UnknownDocumentStore(
            'getting document stores for backend {} is not supported!'.format(topic)
        )
