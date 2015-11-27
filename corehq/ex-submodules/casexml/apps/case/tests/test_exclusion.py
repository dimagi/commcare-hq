from django.test import TestCase
import os
from django.test.utils import override_settings
from casexml.apps.case.tests.util import delete_all_cases
from corehq.apps.receiverwrapper import submit_form_locally
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors
from corehq.form_processor.tests.utils import run_with_all_backends

TEST_DOMAIN = 'test-domain'


@override_settings(CASEXML_FORCE_DOMAIN_CHECK=False)
class CaseExclusionTest(TestCase):
    """
    Tests the exclusion of device logs from case processing
    """
    
    def setUp(self):
        delete_all_cases()

    @run_with_all_backends
    def testTopLevelExclusion(self):
        """
        Entire forms tagged as device logs should be excluded
        """
        file_path = os.path.join(os.path.dirname(__file__), "data", "exclusion", "device_report.xml")
        with open(file_path, "rb") as f:
            xml_data = f.read()

        submit_form_locally(xml_data, TEST_DOMAIN)
        self.assertEqual(0, len(CaseAccessors(TEST_DOMAIN).get_case_ids_in_domain()))

    @run_with_all_backends
    def testNestedExclusion(self):
        """
        Blocks inside forms tagged as device logs should be excluded
        """
        file_path = os.path.join(os.path.dirname(__file__), "data", "exclusion", "nested_device_report.xml")
        with open(file_path, "rb") as f:
            xml_data = f.read()
        _, _, [case] = submit_form_locally(xml_data, TEST_DOMAIN)
        self.assertEqual(['case_in_form'], CaseAccessors(TEST_DOMAIN).get_case_ids_in_domain())
        self.assertEqual("form case", case.name)
