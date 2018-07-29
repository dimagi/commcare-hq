from __future__ import absolute_import
from __future__ import unicode_literals
import os

from django.test import TestCase

from corehq.apps.receiverwrapper.util import submit_form_locally
from corehq.form_processor.tests.utils import use_sql_backend
from corehq.util.test_utils import TestFileMixin


class TestNamespaces(TestCase, TestFileMixin):
    file_path = ('data', 'posts')
    root = os.path.dirname(__file__)

    def _assert_xmlns(self, xmlns, xform, xpath, expect_xmlns_index=False):
        result = xform.get_data(xpath)
        self.assertEqual(xmlns, result['@xmlns'] if expect_xmlns_index else result)

    def testClosed(self):
        xml_data = self.get_xml('namespaces')
        xform = submit_form_locally(xml_data, 'test-domain').xform

        self.assertEqual("http://commcarehq.org/test/ns", xform.xmlns)
        self._assert_xmlns('no namespace here', xform, 'form/empty')
        self._assert_xmlns('http://commcarehq.org/test/flatns', xform, 'form/flat', True)
        self._assert_xmlns('http://commcarehq.org/test/parent', xform, 'form/parent', True)
        self._assert_xmlns('cwo', xform, 'form/parent/childwithout')
        self._assert_xmlns('http://commcarehq.org/test/child1', xform, 'form/parent/childwith', True)
        self._assert_xmlns('http://commcarehq.org/test/child2', xform, 'form/parent/childwithelement', True)
        self._assert_xmlns('gc', xform, 'form/parent/childwithelement/grandchild')
        self._assert_xmlns('lcwo', xform, 'form/parent/lastchildwithout')
        self._assert_xmlns('nothing here either', xform, 'form/lastempty')


@use_sql_backend
class TestNamespacesSQL(TestNamespaces):
    pass
