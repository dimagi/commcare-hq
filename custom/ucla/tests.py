from collections import namedtuple
import uuid
from django.test import TestCase

from corehq.apps.fixtures.models import (
    FixtureDataType, FixtureTypeField, FixtureDataItem, FieldList, FixtureItemField
)
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

    def _reminder(self):
        return Reminder(
            domain=self.domain,
            schedule_iteration_num=0,
            current_event_sequence_num=0,
        )

    def _handler(self, num_events=0):
        return Handler(events=[None] * num_events)

    def _setup_fixture_type(self):
        self.data_type = FixtureDataType(
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
        self.data_type.save()
        self.addCleanup(self.data_type.delete)
        self._setup_data_item()

    def _setup_data_item(self, risk='risk1', sequence='1', message='message1'):
        data_item = FixtureDataItem(
            domain=self.domain,
            data_type_id=self.data_type.get_id,
            fields={
                "risk_profile": FieldList(
                    field_list=[
                        FixtureItemField(
                            field_value=risk,
                            properties={}
                        )
                    ]
                ),
                "sequence": FieldList(
                    field_list=[
                        FixtureItemField(
                            field_value=sequence,
                            properties={}
                        )
                    ]
                ),
                "message": FieldList(
                    field_list=[
                        FixtureItemField(
                            field_value=message,
                            properties={}
                        )
                    ]
                ),
            },
            item_attributes={},
        )
        data_item.save()
        self.addCleanup(data_item.delete)

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
        self._setup_fixture_type()
        self.assertIsNone(ucla_message_bank_content(self._reminder(), self._handler(), None))

    @run_with_all_backends
    def test_passing_case_without_risk_profile(self):
        self._setup_fixture_type()
        with create_test_case(self.domain, self.case_type, 'test-case') as case:
            self.assertIsNone(ucla_message_bank_content(self._reminder(), self._handler(), case))

    @run_with_all_backends
    def test_no_relevant_message_invalid_risk(self):
        self._setup_fixture_type()
        with create_test_case(self.domain, self.case_type, 'test-case', {'risk_profile': 'risk2'}) as case:
            self.assertIsNone(ucla_message_bank_content(self._reminder(), self._handler(), case))

    @run_with_all_backends
    def test_no_relevant_message_invalid_seq_num(self):
        self._setup_fixture_type()
        with create_test_case(self.domain, self.case_type, 'test-case', {'risk_profile': 'risk1'}) as case:
            self.assertIsNone(ucla_message_bank_content(self._reminder(), self._handler(num_events=1), case))

    @run_with_all_backends
    def test_multiple_relevant_messages(self):
        self._setup_fixture_type()
        self._setup_data_item('risk1', '1', 'message2')
        with create_test_case(self.domain, self.case_type, 'test-case', {'risk_profile': 'risk1'}) as case:
            self.assertIsNone(ucla_message_bank_content(self._reminder(), self._handler(), case))

    @run_with_all_backends
    def test_correct_message(self):
        self._setup_fixture_type()
        with create_test_case(self.domain, self.case_type, 'test-case', {'risk_profile': 'risk1'}) as case:
            self.assertEqual(ucla_message_bank_content(self._reminder(), self._handler(), case), 'message1')
