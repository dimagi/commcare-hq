from __future__ import absolute_import
from django.test import SimpleTestCase
from corehq.apps.change_feed.document_types import CASE, get_doc_meta_object_from_document, FORM, DOMAIN, \
    change_meta_from_doc, COMMCARE_USER, WEB_USER, GROUP
from corehq.apps.change_feed.exceptions import MissingMetaInformationError
from corehq.util.test_utils import generate_cases


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


@generate_cases([
    # primary type tests
    ({'doc_type': 'CommCareCase'}, CASE),
    ({'doc_type': 'XFormInstance'}, FORM),
    ({'doc_type': 'XFormArchived'}, FORM),
    ({'doc_type': 'XFormDeprecated'}, FORM),
    ({'doc_type': 'XFormDuplicate'}, FORM),
    ({'doc_type': 'XFormError'}, FORM),
    ({'doc_type': 'Domain'}, DOMAIN),
    ({'doc_type': 'CommCareUser'}, COMMCARE_USER),
    ({'doc_type': 'WebUser'}, WEB_USER),
    ({'doc_type': 'Group'}, GROUP),
    # subtype tests
    ({'doc_type': 'CommCareCase', 'type': 'person'}, CASE, 'person'),
    ({'doc_type': 'XFormInstance', 'xmlns': 'my-xmlns'}, FORM, 'my-xmlns'),
    # domain tests
    ({'doc_type': 'CommCareCase', 'domain': 'test-domain'}, CASE, None, 'test-domain'),
    ({'doc_type': 'XFormInstance', 'domain': 'test-domain'}, FORM, None, 'test-domain'),
    ({'doc_type': 'Domain', 'name': 'test-domain'}, DOMAIN, None, 'test-domain'),
    ({'doc_type': 'Domain', 'domain': 'wrong', 'name': 'right'}, DOMAIN, None, 'right'),
    # deletion tests
    ({'doc_type': 'CommCareCase-Deleted'}, CASE, None, None, True),
    ({'doc_type': 'XFormInstance-Deleted'}, FORM, None, None, True),
    ({'doc_type': 'Domain-Deleted'}, DOMAIN, None, None, True),
    ({'doc_type': 'Domain-DUPLICATE'}, DOMAIN, None, None, True),
    ({'doc_type': 'CommCareUser-Deleted'}, COMMCARE_USER, None, None, True),
    ({'doc_type': 'WebUser-Deleted'}, WEB_USER, None, None, True),
    ({'doc_type': 'Group-Deleted'}, GROUP, None, None, True),
], DocumentTypeTest)
def test_document_meta(self, raw_doc, expected_primary_type, expected_subtype=None,
                       expected_domain=None, expected_deletion=False):
    doc_meta = get_doc_meta_object_from_document(raw_doc)
    self.assertEqual(expected_primary_type, doc_meta.primary_type)
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
