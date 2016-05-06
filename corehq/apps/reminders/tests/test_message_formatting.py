from casexml.apps.case.models import CommCareCase
from casexml.apps.case.sharedmodels import CommCareCaseIndex
from corehq.apps.reminders.event_handlers import get_message_template_params
from corehq.apps.reminders.models import Message
from corehq.apps.reminders.tests.utils import BaseReminderTestCase
from corehq.form_processor.tests.utils import set_case_property_directly
from datetime import datetime, timedelta


class MessageTestCase(BaseReminderTestCase):

    def setUp(self):
        self.domain = "test"

        self.parent_case = CommCareCase(
            domain=self.domain,
            type="parent",
            name="P001",
        )
        set_case_property_directly(self.parent_case, "parent_prop1", "abc")
        self.parent_case.save()

        self.child_case = CommCareCase(
            domain=self.domain,
            type="child",
            name="P002",
            indices=[CommCareCaseIndex(
                identifier="parent",
                referenced_type="parent",
                referenced_id=self.parent_case._id,
            )],
        )
        set_case_property_directly(self.child_case, "child_prop1", "def")
        self.child_case.save()

    def tearDown(self):
        self.child_case.delete()
        self.parent_case.delete()

    def test_message(self):
        message = 'The EDD for client with ID {case.external_id} is approaching in {case.edd.days_until} days.'
        case = {'external_id': 123, 'edd': datetime.utcnow() + timedelta(days=30)}
        outcome = 'The EDD for client with ID 123 is approaching in 30 days.'
        self.assertEqual(Message.render(message, case=case), outcome)

    def test_template_params(self):
        child_result = {"case": self.child_case.case_properties()}
        child_result["case"]["parent"] = self.parent_case.case_properties()
        self.assertEqual(
            get_message_template_params(self.child_case), child_result)

        parent_result = {"case": self.parent_case.case_properties()}
        parent_result["case"]["parent"] = {}
        self.assertEqual(
            get_message_template_params(self.parent_case), parent_result)
