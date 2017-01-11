from collections import namedtuple
import uuid
from django.test import TestCase

from corehq.apps.fixtures.models import FixtureDataType, FixtureTypeField
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors
from corehq.form_processor.tests.utils import run_with_all_backends
from corehq.util.test_utils import create_test_case
from custom.ucla.api import ucla_message_bank_content

Reminder = namedtuple('Reminder', ['domain', 'schedule_iteration_num', 'current_event_sequence_num'])
Handler = namedtuple('Handler', ['events'])


class UCLACustomHandler(TestCase):
    domain = uuid.uuid4().hex
    case_type = 'ucla-reminder'
    fixture_name = 'message_bank'

    def setUp(self):
        super(UCLACustomHandler, self).setUp()

    # def tearDown(self):
    #     super(UCLACustomHandler, self).tearDown()

    def _reminder(self):
        return Reminder(
            domain=self.domain,
            schedule_iteration_num=0,
            current_event_sequence_num=0,
        )

    def _handler(self):
        return Handler(events=[])

    @run_with_all_backends
    def test_message_bank_doesnt_exist(self):
        with create_test_case(self.domain, self.case_type, 'test-case') as case:
            self.assertIsNone(ucla_message_bank_content(self._reminder(), self._handler(), case))

    @run_with_all_backends
    def test_message_bank_doesnt_have_correct_properties(self):
        data_type = FixtureDataType(
            domain=self.domain,
            tag=self.fixture_name,
            fields=[],
            item_attributes=[]
        )
        data_type.save()
        self.addCleanup(data_type.delete)
        with create_test_case(self.domain, self.case_type, 'test-case') as case:
            self.assertIsNone(ucla_message_bank_content(self._reminder(), self._handler(), case))

    def test_not_passing_case(self):
        data_type = FixtureDataType(
            domain=self.domain,
            tag=self.fixture_name,
            fields=[
                FixtureTypeField(
                    field_name="risk_profile",
                    properties=[]
                ),
                FixtureTypeField(
                    field_name="sequence",
                    properties=[]
                ),
                FixtureTypeField(
                    field_name="message",
                    properties=[]
                ),
            ],
            item_attributes=[]
        )
        data_type.save()
        self.addCleanup(data_type.delete)
        self.assertIsNone(ucla_message_bank_content(self._reminder(), self._handler(), None))
