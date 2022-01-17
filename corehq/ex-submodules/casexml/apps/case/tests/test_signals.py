from django.test import TestCase
from casexml.apps.case.mock import CaseFactory
from casexml.apps.case.signals import cases_received
from casexml.apps.case.xform import process_cases_with_casedb
from corehq.form_processor.backends.sql.dbaccessors import FormAccessorSQL
from corehq.form_processor.interfaces.processor import FormProcessorInterface
from corehq.form_processor.models import CommCareCaseSQL


class TestCasesReceivedSignal(TestCase):

    def test_casedb_already_has_cases(self):
        casedb_cache = FormProcessorInterface().casedb_cache
        case = CaseFactory().create_case()
        case_db = casedb_cache(initial=[
            CommCareCaseSQL(case_id='fake1'),
            CommCareCaseSQL(case_id='fake2'),
        ])
        form = FormAccessorSQL.get_form(case.xform_ids[0])

        def assert_exactly_one_case(sender, xform, cases, **kwargs):
            global case_count
            case_count = len(cases)

        cases_received.connect(assert_exactly_one_case)
        try:
            process_cases_with_casedb([form], case_db)
            self.assertEqual(1, case_count)
        finally:
            cases_received.disconnect(assert_exactly_one_case)
