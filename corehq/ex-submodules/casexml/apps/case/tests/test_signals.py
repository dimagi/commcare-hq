from django.test import TestCase
from casexml.apps.case.mock import CaseFactory
from casexml.apps.case.models import CommCareCase
from casexml.apps.case.signals import cases_received
from casexml.apps.case.xform import CaseDbCache, process_cases_with_casedb
from couchforms.models import XFormInstance


class TestCasesReceivedSignal(TestCase):

    def test_casedb_already_has_cases(self):
        case = CaseFactory().create_case()
        case_db = CaseDbCache(initial=[CommCareCase(_id='fake1'), CommCareCase(_id='fake2')])
        form = XFormInstance.get(case.xform_ids[0])

        def assert_exactly_one_case(sender, xform, cases, **kwargs):
            global case_count
            case_count = len(cases)

        cases_received.connect(assert_exactly_one_case)
        try:
            process_cases_with_casedb([form], case_db)
            self.assertEqual(1, case_count)
        finally:
            cases_received.disconnect(assert_exactly_one_case)
