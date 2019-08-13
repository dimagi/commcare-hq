from __future__ import absolute_import
from __future__ import unicode_literals

from django.test import SimpleTestCase, override_settings

from casexml.apps.phone.document_store import ReadonlySyncLogDocumentStore
from corehq.apps.change_feed import data_sources
from corehq.apps.change_feed.data_sources import get_document_store
from corehq.apps.change_feed.exceptions import UnknownDocumentStore
from corehq.apps.locations.document_store import ReadonlyLocationDocumentStore
from corehq.apps.sms.document_stores import ReadonlySMSDocumentStore
from corehq.form_processor.document_stores import (
    DocStoreLoadTracker,
    ReadonlyCaseDocumentStore,
    ReadonlyFormDocumentStore,
)
from corehq.util.exceptions import DatabaseNotFound
from corehq.util.test_utils import generate_cases
from pillowtop.dao.couch import CouchDocumentStore


class DocumentStoreTests(SimpleTestCase):
    def test_missing_db(self):
        with self.assertRaises(DatabaseNotFound):
            get_document_store(data_sources.SOURCE_COUCH, 'baddb', 'domain')

    def test_unknown_store(self):
        with self.assertRaises(UnknownDocumentStore):
            get_document_store(data_sources.SOURCE_SQL, 'badsource', 'domain')


@generate_cases([
    (data_sources.SOURCE_COUCH, 'test_commcarehq', CouchDocumentStore),

    # legacy
    (data_sources.CASE_SQL, '', ReadonlyCaseDocumentStore, True),
    (data_sources.FORM_SQL, '', ReadonlyFormDocumentStore, True),
    (data_sources.LOCATION, '', ReadonlyLocationDocumentStore),
    (data_sources.SYNCLOG_SQL, '', ReadonlySyncLogDocumentStore),
    (data_sources.SMS, '', ReadonlySMSDocumentStore),

    (data_sources.SOURCE_SQL, data_sources.CASE_SQL, ReadonlyCaseDocumentStore, True),
    (data_sources.SOURCE_SQL, data_sources.FORM_SQL, ReadonlyFormDocumentStore, True),
    (data_sources.SOURCE_SQL, data_sources.LOCATION, ReadonlyLocationDocumentStore),
    (data_sources.SOURCE_SQL, data_sources.SYNCLOG_SQL, ReadonlySyncLogDocumentStore),
    (data_sources.SOURCE_SQL, data_sources.SMS, ReadonlySMSDocumentStore),

], DocumentStoreTests)
def test_get_document_store(self, source_type, source_name, expected, sql_domain=False):
    with override_settings(TESTS_SHOULD_USE_SQL_BACKEND=sql_domain):
        store = get_document_store(source_type, source_name, 'domain')
    if isinstance(store, DocStoreLoadTracker):
        store = store.store
    self.assertEqual(store.__class__, expected)
