from django.test import TestCase

from corehq.apps.receiverwrapper.util import submit_form_locally
from corehq.util.test_utils import TestFileMixin
from couchforms.models import DefaultAuthContext
import os

from corehq.form_processor.tests.utils import run_with_all_backends


class AuthTest(TestCase, TestFileMixin):
    file_path = ('data', 'posts')
    root = os.path.dirname(__file__)

    @run_with_all_backends
    def test_auth_context(self):
        xml_data = self.get_xml('meta')

        _, xform, _ = submit_form_locally(xml_data, 'test-domain', auth_context=DefaultAuthContext())
        self.assertEqual(xform.auth_context, {'doc_type': 'DefaultAuthContext'})
