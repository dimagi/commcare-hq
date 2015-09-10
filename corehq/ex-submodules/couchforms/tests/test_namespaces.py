import os
from django.test import TestCase

from corehq.form_processor.interfaces import FormProcessorInterface


class TestNamespaces(TestCase):

    def _assert_xmlns(self, xmlns, xform, xpath, expect_xmlns_index=False):
        result = xform.get_data(xpath)
        self.assertEqual(xmlns, result['@xmlns'] if expect_xmlns_index else result)

    def testClosed(self):
        file_path = os.path.join(os.path.dirname(__file__), "data", "namespaces.xml")
        xml_data = open(file_path, "rb").read()
        xform = FormProcessorInterface.post_xform(xml_data)

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
