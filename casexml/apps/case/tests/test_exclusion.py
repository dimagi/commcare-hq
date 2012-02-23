from django.test import TestCase
import os
from casexml.apps.case.models import CommCareCase
from couchforms.util import post_xform_to_couch
from casexml.apps.case.signals import process_cases

class CaseExclusionTest(TestCase):
    """
    Tests the exclusion of device logs from case processing
    """
    
    def setUp(self):
        for item in CommCareCase.view("case/by_user", include_docs=True, reduce=False).all():
            item.delete()
        
    def testTopLevelExclusion(self):
        """
        Entire forms tagged as device logs should be excluded
        """
        self.assertEqual(0, len(CommCareCase.view("case/by_user", include_docs=True, reduce=False).all()))
        file_path = os.path.join(os.path.dirname(__file__), "data", "exclusion", "device_report.xml")
        with open(file_path, "rb") as f:
            xml_data = f.read()
        form = post_xform_to_couch(xml_data)
        process_cases(sender="testharness", xform=form)
        self.assertEqual(0, len(CommCareCase.view("case/by_user", include_docs=True, reduce=False).all()))
        
    def testNestedExclusion(self):
        """
        Blocks inside forms tagged as device logs should be excluded
        """
        self.assertEqual(0, len(CommCareCase.view("case/by_user", include_docs=True, reduce=False).all()))
        file_path = os.path.join(os.path.dirname(__file__), "data", "exclusion", "nested_device_report.xml")
        with open(file_path, "rb") as f:
            xml_data = f.read()
        form = post_xform_to_couch(xml_data)
        process_cases(sender="testharness", xform=form)
        self.assertEqual(1, len(CommCareCase.view("case/by_user", include_docs=True, reduce=False).all()))
        case = CommCareCase.get("case_in_form")
        self.assertEqual("form case", case.name)
        
