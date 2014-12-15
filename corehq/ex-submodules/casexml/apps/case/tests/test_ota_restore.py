from django.test import TestCase
import os
from django.test.utils import override_settings
from casexml.apps.case.models import CommCareCase
from casexml.apps.case import process_cases
from casexml.apps.case.tests import delete_all_cases
from couchforms.tests.testutils import post_xform_to_couch


@override_settings(CASEXML_FORCE_DOMAIN_CHECK=False)
class TestOTARestore(TestCase):
    
    def setUp(self):
        delete_all_cases()

    def testOTARestore(self):
        self.assertEqual(0, len(CommCareCase.view("case/by_user", reduce=False).all()))
        file_path = os.path.join(os.path.dirname(__file__), "data", "multicase", "parallel_cases.xml")
        with open(file_path, "rb") as f:
            xml_data = f.read()
        form = post_xform_to_couch(xml_data)
        process_cases(form)
        self.assertEqual(4, len(CommCareCase.view("case/by_user", reduce=False).all()))
        
    def testMixed(self):
        self.assertEqual(0, len(CommCareCase.view("case/by_user", reduce=False).all()))
        file_path = os.path.join(os.path.dirname(__file__), "data", "multicase", "mixed_cases.xml")
        with open(file_path, "rb") as f:
            xml_data = f.read()
        form = post_xform_to_couch(xml_data)
        process_cases(form)
        self.assertEqual(4, len(CommCareCase.view("case/by_user", reduce=False).all()))
