from django.test import TestCase
from couchforms.models import DefaultAuthContext
from couchforms.tests.testutils import post_xform_to_couch
import os


class AuthTest(TestCase):

    def test_auth_context(self):
        file_path = os.path.join(os.path.dirname(__file__), "data", "meta.xml")
        xml_data = open(file_path, "rb").read()

        def process(xform):
            xform['auth_context'] = DefaultAuthContext().to_json()

        xform = post_xform_to_couch(xml_data, process=process)
        self.assertEqual(xform.auth_context, {'doc_type': 'DefaultAuthContext'})
