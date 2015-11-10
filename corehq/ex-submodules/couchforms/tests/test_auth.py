from django.test import TestCase
from couchforms.models import DefaultAuthContext
import os

from corehq.form_processor.test_utils import run_with_all_backends
from corehq.form_processor.interfaces.processor import FormProcessorInterface


class AuthTest(TestCase):

    @run_with_all_backends
    def test_auth_context(self):
        file_path = os.path.join(os.path.dirname(__file__), "data", "meta.xml")
        xml_data = open(file_path, "rb").read()

        def process(xform):
            xform.auth_context = DefaultAuthContext().to_json()

        xform = FormProcessorInterface().post_xform(xml_data, process=process)
        self.assertEqual(xform.auth_context, {'doc_type': 'DefaultAuthContext'})
