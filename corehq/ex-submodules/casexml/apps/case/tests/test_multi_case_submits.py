from django.test import TestCase
import os
from django.test.utils import override_settings
from casexml.apps.case.tests.util import delete_all_xforms, delete_all_cases
from corehq.apps.receiverwrapper import submit_form_locally
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors


@override_settings(CASEXML_FORCE_DOMAIN_CHECK=False)
class MultiCaseTest(TestCase):

    def setUp(self):
        super(MultiCaseTest, self).setUp()
        self.domain = 'gigglyfoo'
        delete_all_xforms()
        delete_all_cases()

    @override_settings(TESTS_SHOULD_USE_SQL_BACKEND=False)
    def testParallel(self):
        file_path = os.path.join(os.path.dirname(__file__), "data", "multicase", "parallel_cases.xml")
        with open(file_path, "rb") as f:
            xml_data = f.read()

        _, form, cases = submit_form_locally(xml_data, domain=self.domain)
        self.assertEqual(4, len(cases))
        self._check_ids(form, cases)

    @override_settings(TESTS_SHOULD_USE_SQL_BACKEND=False)
    def testMixed(self):
        file_path = os.path.join(os.path.dirname(__file__), "data", "multicase", "mixed_cases.xml")
        with open(file_path, "rb") as f:
            xml_data = f.read()
        _, form, cases = submit_form_locally(xml_data, domain=self.domain)
        self.assertEqual(4, len(cases))
        self._check_ids(form, cases)

    @override_settings(TESTS_SHOULD_USE_SQL_BACKEND=False)
    def testCasesInRepeats(self):
        file_path = os.path.join(os.path.dirname(__file__), "data", "multicase", "case_in_repeats.xml")
        with open(file_path, "rb") as f:
            xml_data = f.read()
        _, form, cases = submit_form_locally(xml_data, domain=self.domain)
        self.assertEqual(3, len(cases))
        self._check_ids(form, cases)

    def _check_ids(self, form, cases):
        for case in cases:
            ids = CaseAccessors().get_case_xform_ids(case.case_id)
            self.assertEqual(1, len(ids))
            self.assertEqual(form._id, ids[0])
