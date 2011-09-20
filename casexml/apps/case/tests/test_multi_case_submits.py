from django.test import TestCase
import os
from casexml.apps.case.models import CommCareCase
from couchforms.util import post_xform_to_couch
from casexml.apps.case.signals import process_cases

class MultiCaseTest(TestCase):
    
    def setUp(self):
        for item in CommCareCase.view("case/by_xform_id", include_docs=True).all():
            item.delete()
        
    def testParallel(self):
        self.assertEqual(0, len(CommCareCase.view("case/by_xform_id").all()))
        file_path = os.path.join(os.path.dirname(__file__), "data", "multicase", "parallel_cases.xml")
        with open(file_path, "rb") as f:
            xml_data = f.read()
        form = post_xform_to_couch(xml_data)
        process_cases(sender="testharness", xform=form)
        self.assertEqual(4, len(CommCareCase.view("case/by_xform_id").all()))
        
    def testMixed(self):
        self.assertEqual(0, len(CommCareCase.view("case/by_xform_id").all()))
        file_path = os.path.join(os.path.dirname(__file__), "data", "multicase", "mixed_cases.xml")
        with open(file_path, "rb") as f:
            xml_data = f.read()
        form = post_xform_to_couch(xml_data)
        process_cases(sender="testharness", xform=form)
        self.assertEqual(4, len(CommCareCase.view("case/by_xform_id").all()))
        
        
    def testCasesInRepeats(self):
        self.assertEqual(0, len(CommCareCase.view("case/by_xform_id").all()))
        file_path = os.path.join(os.path.dirname(__file__), "data", "multicase", "case_in_repeats.xml")
        with open(file_path, "rb") as f:
            xml_data = f.read()
        form = post_xform_to_couch(xml_data)
        process_cases(sender="testharness", xform=form)
        self.assertEqual(3, len(CommCareCase.view("case/by_xform_id").all()))
        
        
        