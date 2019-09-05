from django.test import TestCase

from casexml.apps.case.mock import CaseFactory, CaseStructure
from casexml.apps.case.tests.util import delete_all_cases, delete_all_xforms
from casexml.apps.case.util import get_case_history
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors
from corehq.form_processor.tests.utils import run_with_all_backends


class TestCaseHistory(TestCase):
    def setUp(self):
        self.domain = "isildur"
        self.factory = CaseFactory(self.domain)
        self.case = self.factory.create_case(owner_id='owner', case_name="Aragorn", update={"prop_1": "val1"})
        self.other_case = self.factory.create_case()

    def tearDown(self):
        delete_all_xforms()
        delete_all_cases()

    @run_with_all_backends
    def test_case_history(self):
        self.factory.create_or_update_case(
            CaseStructure(
                self.case.case_id,
                attrs={
                    "update": {
                        'prop_1': "val1",
                        'prop_2': "val1",
                        'prop_3': "val1",
                    },
                }),
        )
        self.factory.create_or_update_case(
            CaseStructure(
                self.case.case_id,
                attrs={
                    "update": {
                        'prop_1': "val2",
                        'prop_2': "val2",
                        'prop_4': "val",
                    },
                }),
        )
        case = CaseAccessors(self.domain).get_case(self.case.case_id)
        history = get_case_history(case)
        self.assertEqual(history[0]['prop_1'], "val1")
        self.assertEqual(history[1]['prop_2'], "val1")
        self.assertEqual(history[2]['prop_2'], "val2")
