from django.test import TestCase

from corehq.util.test_utils import TestFileMixin
from couchforms.models import DefaultAuthContext
import os

from corehq.form_processor.tests.utils import run_with_all_backends, post_xform


class AuthTest(TestCase, TestFileMixin):
    file_path = ('data', 'posts')
    root = os.path.dirname(__file__)

    @run_with_all_backends
    def test_auth_context(self):
        xml_data = self.get_xml('meta')

        def process(xform):
            xform.auth_context = DefaultAuthContext().to_json()

        xform = post_xform(xml_data, process=process)
        self.assertEqual(xform.auth_context, {'doc_type': 'DefaultAuthContext'})
