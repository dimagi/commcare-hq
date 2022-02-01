from django.test import TestCase
from casexml.apps.case.mock import CaseFactory
from casexml.apps.case.signals import cases_received
from casexml.apps.case.xform import process_cases_with_casedb
from corehq.form_processor.interfaces.processor import FormProcessorInterface
from corehq.form_processor.models import CommCareCase, XFormInstance


class TestCasesReceivedSignal(TestCase):

    def test_casedb_already_has_cases(self):
        casedb_cache = FormProcessorInterface().casedb_cache
        case = CaseFactory().create_case()
        case_db = casedb_cache(initial=[
            CommCareCase(case_id='fake1'),
            CommCareCase(case_id='fake2'),
        ])
        form = XFormInstance.objects.get_form(case.xform_ids[0])
        received = []

        def receive_cases(sender, xform, cases, **kwargs):
            received.extend(cases)

        cases_received.connect(receive_cases)
        try:
            process_cases_with_casedb([form], case_db)
            self.assertEqual(len(received), 1)
        finally:
            cases_received.disconnect(receive_cases)
