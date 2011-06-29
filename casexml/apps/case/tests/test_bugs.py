from django.test import TestCase
import os
from casexml.apps.case.models import CommCareCase
from couchforms.util import post_xform_to_couch
from casexml.apps.case.signals import process_cases

class CaseBugTest(TestCase):
    """
    Tests bugs that come up in case processing
    """
    
    def setUp(self):
        for item in CommCareCase.view("case/by_xform_id", include_docs=True).all():
            item.delete()
        
    def testConflictingIds(self):
        """
        If two forms share an ID it's a conflict
        """
        self.assertEqual(0, len(CommCareCase.view("case/by_xform_id").all()))
        file_path = os.path.join(os.path.dirname(__file__), "data", "bugs", "id_conflicts.xml")
        with open(file_path, "rb") as f:
            xml_data = f.read()
        form = post_xform_to_couch(xml_data)
        try:
            process_cases(sender="testharness", xform=form)
            self.fail("Previous statement should have raised an exception")
        except Exception:
            pass

        
    def testStringFormatProblems(self):
        """
        If two forms share an ID it's a conflict
        """
        self.assertEqual(0, len(CommCareCase.view("case/by_xform_id").all()))
        file_path = os.path.join(os.path.dirname(__file__), "data", "bugs", "string_formatting.xml")
        with open(file_path, "rb") as f:
            xml_data = f.read()
        form = post_xform_to_couch(xml_data)
        # before the bug was fixed this call failed
        process_cases(sender="testharness", xform=form)
        
    