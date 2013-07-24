from couchforms.util import post_xform_to_couch
import os
from django.utils.unittest.case import TestCase


class AuthTest(TestCase):

    def test_auth_context(self):
        file_path = os.path.join(os.path.dirname(__file__), "data", "meta.xml")
        xml_data = open(file_path, "rb").read()
        xform = post_xform_to_couch(xml_data)
        self.assertEqual(xform.auth_context, {'doc_type': 'DefaultAuthContext'})
