from django.test import SimpleTestCase

from corehq.apps.change_feed.document_types import (
    change_meta_from_doc,
    get_doc_meta_object_from_document,
)
from corehq.apps.change_feed.exceptions import MissingMetaInformationError
from corehq.util.test_utils import generate_cases


class DocumentTypeTest(SimpleTestCase):
    pass


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
], DocumentTypeTest)
def test_document_meta(self, raw_doc, expected_subtype=None,
                       expected_domain=None, expected_deletion=False):
    doc_meta = get_doc_meta_object_from_document(raw_doc)
    self.assertEqual(expected_subtype, doc_meta.subtype)
    self.assertEqual(expected_domain, doc_meta.domain)
    self.assertEqual(expected_deletion, doc_meta.is_deletion)


@generate_cases([
    # primary type tests
    (None,),
    ({},),
    ({'_id': 'id-without-type'},),
    ({'doc_type': 'type-without-id'},),
], DocumentTypeTest)
def test_change_from_doc_failures(self, doc):
    with self.assertRaises(MissingMetaInformationError):
        change_meta_from_doc(doc, 'dummy-data-source', 'dummy-data-source-name')


@generate_cases([
    ({'_id': 'id', 'doc_type': 'CommCareCase', 'domain': 'test-domain'}, 'id'),
], DocumentTypeTest)
def test_change_from_doc_success(self, doc, expected_id):
    change_meta = change_meta_from_doc(doc, 'dummy-data-source', 'dummy-data-source-name')
    doc_meta = get_doc_meta_object_from_document(doc)
    self.assertEqual(expected_id, change_meta.document_id)
    self.assertEqual('dummy-data-source', change_meta.data_source_type)
    self.assertEqual('dummy-data-source-name', change_meta.data_source_name)
    self.assertEqual(doc_meta.raw_doc_type, change_meta.document_type)
    self.assertEqual(doc_meta.subtype, change_meta.document_subtype)
    self.assertEqual(doc_meta.domain, change_meta.domain)
    self.assertEqual(doc_meta.is_deletion, change_meta.is_deletion)
