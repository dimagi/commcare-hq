from __future__ import absolute_import
from __future__ import unicode_literals
from django.test import TestCase

from corehq.apps.receiverwrapper.util import submit_form_locally
from corehq.util.test_utils import TestFileMixin
from couchforms.models import DefaultAuthContext
import os

from corehq.form_processor.tests.utils import use_sql_backend


class AuthTest(TestCase, TestFileMixin):
    file_path = ('data', 'posts')
    root = os.path.dirname(__file__)

    def test_auth_context(self):
        xml_data = self.get_xml('meta')

        result = submit_form_locally(xml_data, 'test-domain', auth_context=DefaultAuthContext())
        self.assertEqual(result.xform.auth_context, {'doc_type': 'DefaultAuthContext'})


@use_sql_backend
class AuthTestSQL(AuthTest):
    pass
