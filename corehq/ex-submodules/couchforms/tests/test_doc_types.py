from django.test import SimpleTestCase
from couchforms import models as couchforms_models


class FormlikeDocTypeTest(SimpleTestCase):

    def test_wrappable(self):
        types = couchforms_models.all_known_formlike_doc_types()
        for key in couchforms_models.doc_types().keys():
            self.assertTrue(key in types)

    def test_deleted(self):
        self.assertTrue('XFormInstance-Deleted' in couchforms_models.all_known_formlike_doc_types())
