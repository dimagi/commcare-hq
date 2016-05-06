from corehq.apps.reminders.event_handlers import get_message_template_params
from corehq.apps.reminders.models import Message
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors
from corehq.form_processor.tests.utils import run_with_all_backends
from corehq.util.test_utils import create_test_case, set_parent_case
from datetime import datetime, timedelta
from django.test import TestCase


class MessageTestCase(TestCase):

    def setUp(self):
        self.domain = 'message-formatting-test'

    def test_message(self):
        message = 'The EDD for client with ID {case.external_id} is approaching in {case.edd.days_until} days.'
        case_json = {'external_id': 123, 'edd': datetime.utcnow() + timedelta(days=30)}
        expected = 'The EDD for client with ID 123 is approaching in 30 days.'
        self.assertEqual(Message.render(message, case=case_json), expected)

    def create_child_case(self):
        return create_test_case(self.domain, 'child', 'P002', case_properties={'child_prop1': 'def'})

    def create_parent_case(self):
        return create_test_case(self.domain, 'parent', 'P001', case_properties={'parent_prop1': 'abc'})

    @run_with_all_backends
    def test_template_params(self):
        with self.create_child_case() as child_case, self.create_parent_case() as parent_case:
            set_parent_case(self.domain, child_case, parent_case)
            child_case = CaseAccessors(self.domain).get_case(child_case.case_id)
            parent_case = CaseAccessors(self.domain).get_case(parent_case.case_id)

            child_result = {'case': child_case.to_json()}
            child_result['case']['parent'] = parent_case.to_json()
            self.assertEqual(get_message_template_params(child_case), child_result)

            parent_result = {'case': parent_case.to_json()}
            parent_result['case']['parent'] = {}
            self.assertEqual(get_message_template_params(parent_case), parent_result)
