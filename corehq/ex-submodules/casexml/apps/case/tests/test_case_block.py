from django.test import SimpleTestCase
from casexml.apps.case.mock import CaseBlock
from corehq.util.test_utils import flag_disabled, flag_enabled


class TestCaseBlock(SimpleTestCase):

    def test_numeric_properties(self):
        xml = CaseBlock("arbitrary_id", update={'float': float(1.2), 'int': 5}).as_xml()
        self.assertEqual(xml.findtext('update/float'), "1.2")
        self.assertEqual(xml.findtext('update/int'), "5")

    @flag_disabled('USE_CUSTOM_EXTERNAL_ID_CASE_PROPERTY')
    def test_custom_external_id_property_not_used(self):
        domain = "test-domain"
        xml = CaseBlock("arbitrary_id", update={'external_id': "01234"}, external_id="43210", domain=domain)\
            .as_xml()
        self.assertEqual(xml.findtext('update/external_id'), "43210")

    @flag_enabled('USE_CUSTOM_EXTERNAL_ID_CASE_PROPERTY')
    def test_custom_external_id_property_used(self):
        domain = "test-domain"
        xml = CaseBlock("arbitrary_id", update={'external_id': "01234"}, external_id="43210", domain=domain)\
            .as_xml()
        self.assertEqual(xml.findtext('update/external_id'), "01234")
