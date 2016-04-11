from django.test import SimpleTestCase
from corehq.apps.change_feed.document_types import CASE, get_doc_meta_object_from_document, FORM, META, DOMAIN
from corehq.util.test_utils import generate_cases


class DocumentTypeTest(SimpleTestCase):
    pass


@generate_cases([
    # primary type tests
    ({'doc_type': 'CommCareCase'}, CASE),
    ({'doc_type': 'XFormInstance'}, FORM),
    ({'doc_type': 'XFormArchived'}, FORM),
    ({'doc_type': 'XFormDeprecated'}, FORM),
    ({'doc_type': 'XFormDuplicate'}, FORM),
    ({'doc_type': 'XFormError'}, FORM),
    ({'doc_type': 'Domain'}, DOMAIN),
    ({'doc_type': 'CommCareUser'}, META),
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
    ({'doc_type': 'CommCareUser-Deleted'}, META, None, None, True),
], DocumentTypeTest)
def test_document_meta(self, raw_doc, expected_primary_type, expected_subtype=None,
                        expected_domain=None, expected_deletion=False):
    doc_meta = get_doc_meta_object_from_document(raw_doc)
    self.assertEqual(expected_primary_type, doc_meta.primary_type)
    self.assertEqual(expected_subtype, doc_meta.subtype)
    self.assertEqual(expected_domain, doc_meta.domain)
    self.assertEqual(expected_deletion, doc_meta.is_deletion)
