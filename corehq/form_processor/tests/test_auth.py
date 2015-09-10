from django.test import TestCase
from couchforms.models import DefaultAuthContext
import os

from ..interfaces import FormProcessorInterface


class AuthTest(TestCase):

    def test_auth_context(self):
        file_path = os.path.join(os.path.dirname(__file__), "data", "meta.xml")
        xml_data = open(file_path, "rb").read()

        def process(xform):
            xform['auth_context'] = DefaultAuthContext().to_json()

        xform = FormProcessorInterface.post_xform(xml_data, process=process)
        self.assertEqual(xform.to_generic().auth_context, {'doc_type': 'DefaultAuthContext'})
