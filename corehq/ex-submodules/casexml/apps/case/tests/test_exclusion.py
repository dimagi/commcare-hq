from django.test import TestCase
import os
from django.test.utils import override_settings
from casexml.apps.case.models import CommCareCase
from casexml.apps.case.tests.util import delete_all_cases
from corehq.apps.hqcase.dbaccessors import get_total_case_count
from couchforms.tests.testutils import post_xform_to_couch
from casexml.apps.case.xform import process_cases


@override_settings(CASEXML_FORCE_DOMAIN_CHECK=False)
class CaseExclusionTest(TestCase):
    """
    Tests the exclusion of device logs from case processing
    """
    
    def setUp(self):
        delete_all_cases()

    def testTopLevelExclusion(self):
        """
        Entire forms tagged as device logs should be excluded
        """
        file_path = os.path.join(os.path.dirname(__file__), "data", "exclusion", "device_report.xml")
        with open(file_path, "rb") as f:
            xml_data = f.read()
        form = post_xform_to_couch(xml_data)
        process_cases(form)
        self.assertEqual(0, get_total_case_count())
        
    def testNestedExclusion(self):
        """
        Blocks inside forms tagged as device logs should be excluded
        """
        file_path = os.path.join(os.path.dirname(__file__), "data", "exclusion", "nested_device_report.xml")
        with open(file_path, "rb") as f:
            xml_data = f.read()
        form = post_xform_to_couch(xml_data)
        process_cases(form)
        self.assertEqual(1, get_total_case_count())
        case = CommCareCase.get("case_in_form")
        self.assertEqual("form case", case.name)
