from django.test import TestCase
import os
from django.test.utils import override_settings
from casexml.apps.case.models import CommCareCase
from casexml.apps.case.tests import delete_all_xforms, delete_all_cases
from couchforms.models import XFormInstance
from couchforms.tests.testutils import post_xform_to_couch
from casexml.apps.case import process_cases


@override_settings(CASEXML_FORCE_DOMAIN_CHECK=False)
class MultiCaseTest(TestCase):
    
    def setUp(self):
        delete_all_xforms()
        delete_all_cases()

    def testParallel(self):
        self.assertEqual(0, len(CommCareCase.view("case/by_user", reduce=False).all()))
        file_path = os.path.join(os.path.dirname(__file__), "data", "multicase", "parallel_cases.xml")
        with open(file_path, "rb") as f:
            xml_data = f.read()
        form = post_xform_to_couch(xml_data)
        process_cases(form)
        cases = self._get_cases()
        self.assertEqual(4, len(cases))
        self._check_ids(form, cases)

    def testMixed(self):
        self.assertEqual(0, len(CommCareCase.view("case/by_user", reduce=False).all()))
        file_path = os.path.join(os.path.dirname(__file__), "data", "multicase", "mixed_cases.xml")
        with open(file_path, "rb") as f:
            xml_data = f.read()
        form = post_xform_to_couch(xml_data)
        process_cases(form)
        cases = self._get_cases()
        self.assertEqual(4, len(cases))
        self._check_ids(form, cases)



    def testCasesInRepeats(self):
        self.assertEqual(0, len(CommCareCase.view("case/by_user", reduce=False).all()))
        file_path = os.path.join(os.path.dirname(__file__), "data", "multicase", "case_in_repeats.xml")
        with open(file_path, "rb") as f:
            xml_data = f.read()
        form = post_xform_to_couch(xml_data)
        process_cases(form)
        cases = self._get_cases()
        self.assertEqual(3, len(cases))
        self._check_ids(form, cases)

    def _get_cases(self):
        return CommCareCase.view("case/get_lite", reduce=False, include_docs=True).all()

    def _check_ids(self, form, cases):
        for case in cases:
            ids = case.get_xform_ids_from_couch()
            self.assertEqual(1, len(ids))
            self.assertEqual(form._id, ids[0])
