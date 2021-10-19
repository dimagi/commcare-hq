from django.test import SimpleTestCase
from corehq.form_processor.models import XFormInstanceSQL


class FormDocTypesTest(SimpleTestCase):

    def test_doc_types(self):
        for doc_type in XFormInstanceSQL.DOC_TYPE_TO_STATE:
            self.assertIn(doc_type, XFormInstanceSQL.ALL_DOC_TYPES)

    def test_deleted(self):
        self.assertIn('XFormInstance-Deleted', XFormInstanceSQL.ALL_DOC_TYPES)
