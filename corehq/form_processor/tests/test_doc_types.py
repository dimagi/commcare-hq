from django.test import SimpleTestCase
from corehq.form_processor.models import XFormInstance


class FormDocTypesTest(SimpleTestCase):

    def test_doc_types(self):
        for doc_type in XFormInstance.DOC_TYPE_TO_STATE:
            self.assertIn(doc_type, XFormInstance.ALL_DOC_TYPES)

    def test_deleted(self):
        self.assertIn('XFormInstance-Deleted', XFormInstance.ALL_DOC_TYPES)
