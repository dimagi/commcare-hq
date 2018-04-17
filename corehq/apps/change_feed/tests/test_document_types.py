from __future__ import absolute_import
from __future__ import unicode_literals
from django.test import SimpleTestCase

from corehq.apps.change_feed.data_sources import _get_document_store_from_doc_type
from corehq.apps.change_feed.document_types import change_meta_from_doc
from corehq.apps.change_feed.exceptions import MissingMetaInformationError
from corehq.util.couch import get_classes_by_doc_type, get_document_class_by_doc_type
from corehq.util.couchdb_management import couch_config
from corehq.util.test_utils import generate_cases
from pillowtop.dao.couch import CouchDocumentStore


class DocumentTypeTest(SimpleTestCase):

    def test_change_from_doc_success(self):
        change_meta = change_meta_from_doc({
            '_id': 'id',
            'doc_type': 'CommCareCase',
            'domain': 'test-domain',
            'type': 'person'
        })
        self.assertEqual(change_meta.document_id, 'id')
        self.assertEqual(change_meta.document_type, 'CommCareCase')
        self.assertEqual(change_meta.document_subtype, 'person')
        self.assertEqual(change_meta.domain, 'test-domain')
        self.assertEqual(change_meta.is_deletion, False)

    def test_all_doc_types_and_database_covered(self):
        all_doc_types = list(get_classes_by_doc_type())
        for doc_type in sorted(all_doc_types):
            doc_class = get_document_class_by_doc_type(doc_type)
            if doc_class._meta.app_label in ('phone', 'nikshay'):
                continue
            store = _get_document_store_from_doc_type(doc_type, 'domain')
            self.assertIsInstance(store, CouchDocumentStore)
            expected_db = couch_config.get_db_for_doc_type(doc_type)
            self.assertEqual(
                store._couch_db.uri, expected_db.uri,
                "DB mismatch for '{}': {} != {}".format(doc_type, store._couch_db.uri, expected_db.uri)
            )


@generate_cases([
    # primary type tests
    (None,),
    ({},),
    ({'_id': 'id-without-type'},),
    ({'doc_type': 'type-without-id'},),
], DocumentTypeTest)
def test_change_from_doc_failures(self, doc):
    with self.assertRaises(MissingMetaInformationError):
        change_meta_from_doc(doc)


@generate_cases([
    # subtype tests
    ({'doc_type': 'CommCareCase', 'type': 'person'}, 'person'),
    ({'doc_type': 'XFormInstance', 'xmlns': 'my-xmlns'}, 'my-xmlns'),
    # domain tests
    ({'doc_type': 'CommCareCase', 'domain': 'test-domain'}, None, 'test-domain'),
    ({'doc_type': 'XFormInstance', 'domain': 'test-domain'}, None, 'test-domain'),
    ({'doc_type': 'Domain', 'name': 'test-domain'}, None, 'test-domain'),
    ({'doc_type': 'Domain', 'domain': 'wrong', 'name': 'right'}, None, 'right'),
    # deletion tests
    ({'doc_type': 'CommCareCase-Deleted'}, None, None, True),
    ({'doc_type': 'XFormInstance-Deleted'}, None, None, True),
    ({'doc_type': 'Domain-Deleted'}, None, None, True),
    ({'doc_type': 'Domain-DUPLICATE'}, None, None, True),
    ({'doc_type': 'CommCareUser-Deleted'}, None, None, True),
    ({'doc_type': 'WebUser-Deleted'}, None, None, True),
    ({'doc_type': 'Group-Deleted'}, None, None, True),
    # backend id tests
    ({'doc_type': 'CommCareCase', 'backend_id': 'couch'}, None, None, False, 'couch'),
    ({'doc_type': 'CommCareCase', 'backend_id': 'sql'}, None, None, False, 'sql'),
], DocumentTypeTest)
def test_change_meta(self, raw_doc, expected_subtype=None,
                     expected_domain=None, expected_deletion=False,
                     expected_backend_id=None):
    raw_doc['_id'] = 'id'
    change_meta = change_meta_from_doc(raw_doc)
    self.assertEqual(change_meta.document_subtype, expected_subtype)
    self.assertEqual(change_meta.domain, expected_domain)
    self.assertEqual(change_meta.is_deletion, expected_deletion)
    self.assertEqual(change_meta.backend_id, expected_backend_id)
