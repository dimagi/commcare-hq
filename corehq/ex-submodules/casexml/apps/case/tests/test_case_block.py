from django.test import SimpleTestCase
from casexml.apps.case.mock import CaseBlock


class TestCaseBlock(SimpleTestCase):

    def test_numeric_properties(self):
        xml = CaseBlock.deprecated_init("arbitrary_id", update={'float': float(1.2), 'int': 5}).as_xml()
        self.assertEqual(xml.findtext('update/float'), "1.2")
        self.assertEqual(xml.findtext('update/int'), "5")
