from collections import namedtuple
import uuid
from django.test import TestCase

from corehq.apps.domain.models import Domain
from corehq.apps.fixtures.models import Field, LookupTable, LookupTableRow, TypeField
from corehq.messaging.scheduling.models import TimedSchedule, TimedEvent, CustomContent
from corehq.messaging.scheduling.scheduling_partitioned.models import (
    CaseScheduleInstanceMixin,
    CaseTimedScheduleInstance,
    ScheduleInstance,
)
from corehq.apps.users.models import WebUser
from corehq.util.test_utils import create_test_case
from custom.ucla.api import general_health_message_bank_content
from datetime import time

Reminder = namedtuple('Reminder', ['domain', 'schedule_iteration_num', 'current_event_sequence_num'])
Handler = namedtuple('Handler', ['events'])


class TestUCLACustomHandler(TestCase):
    domain_name = uuid.uuid4().hex
    case_type = 'ucla-reminder'
    fixture_name = 'general_health'

    @classmethod
    def setUpClass(cls):
        super(TestUCLACustomHandler, cls).setUpClass()
        cls.domain = Domain.get_or_create_with_name(cls.domain_name, is_active=True)
        email = 'dimagi@dimagi.com'
        cls.user = WebUser.create(cls.domain_name, email, '***', None, None, email=email)
        cls.user.save()
        cls.schedule = TimedSchedule.create_simple_daily_schedule(
            cls.domain_name,
            TimedEvent(time=time(12, 0)),
            CustomContent(custom_content_id='UCLA_GENERAL_HEALTH'),
        )

    @classmethod
    def tearDownClass(cls):
        cls.schedule.delete()
        cls.user.delete(cls.domain.name, deleted_by=None)
        cls.domain.delete()
        super(TestUCLACustomHandler, cls).tearDownClass()

    def _schedule_instance(self, case, iteration_num=1):
        return CaseTimedScheduleInstance(
            domain=self.domain_name,
            case_id=case.case_id,
            recipient_type=CaseScheduleInstanceMixin.RECIPIENT_TYPE_SELF,
            recipient_id=None,
            schedule_iteration_num=iteration_num,
            current_event_num=0,
            timed_schedule_id=self.schedule.schedule_id,
        )

    def _reminder(self, iteration_num=1):
        return Reminder(
            domain=self.domain_name,
            schedule_iteration_num=iteration_num,
            current_event_sequence_num=0,
        )

    def _handler(self):
        return Handler(events=[None])

    def _setup_fixture_type(self):
        self.data_type = LookupTable(
            domain=self.domain_name,
            tag=self.fixture_name,
            fields=[
                TypeField(name="risk_profile"),
                TypeField(name="sequence"),
                TypeField(name="message"),
            ],
            item_attributes=[],
        )
        self.data_type.save()
        self._setup_data_item()

    def _setup_data_item(self, risk='risk1', sequence='1', message='message1'):
        data_item = LookupTableRow(
            domain=self.domain_name,
            table_id=self.data_type.id,
            fields={
                "risk_profile": [Field(value=risk)],
                "sequence": [Field(value=sequence)],
                "message": [Field(value=message)],
            },
            item_attributes={},
            sort_key=0,
        )
        data_item.save()
        self.addCleanup(data_item.delete)

    def _get_current_event_messages(self, schedule_instance):
        content = self.schedule.get_current_event_content(schedule_instance)
        content.set_context(case=schedule_instance.case, schedule_instance=schedule_instance)
        recipients = list(schedule_instance.expand_recipients())
        self.assertEqual(len(recipients), 1)
        return content.get_list_of_messages(recipients[0])

    def test_message_bank_doesnt_exist(self):
        with create_test_case(self.domain_name, self.case_type, 'test-case') as case:
            self.assertRaises(
                AssertionError, general_health_message_bank_content, self._reminder(), self._handler(), case)

    def test_message_bank_doesnt_have_correct_properties(self):
        data_type = LookupTable(
            domain=self.domain_name,
            tag=self.fixture_name,
            fields=[],
            item_attributes=[]
        )
        data_type.save()
        with create_test_case(self.domain_name, self.case_type, 'test-case') as case:
            self.assertRaises(
                AssertionError, general_health_message_bank_content, self._reminder(), self._handler(), case)

    def test_not_passing_case(self):
        self._setup_fixture_type()
        self.assertRaises(
            AssertionError, general_health_message_bank_content, self._reminder(), self._handler(), None)

    def test_passing_case_without_risk_profile(self):
        self._setup_fixture_type()
        with create_test_case(self.domain_name, self.case_type, 'test-case') as case:
            self.assertRaises(
                AssertionError, general_health_message_bank_content, self._reminder(), self._handler(), case)

    def test_no_relevant_message_invalid_risk(self):
        self._setup_fixture_type()
        with create_test_case(self.domain_name, self.case_type, 'test-case', {'risk_profile': 'risk2'}) as case:
            self.assertRaises(
                AssertionError, general_health_message_bank_content, self._reminder(), self._handler(), case)

    def test_no_relevant_message_invalid_seq_num(self):
        self._setup_fixture_type()
        with create_test_case(self.domain_name, self.case_type, 'test-case', {'risk_profile': 'risk1'}) as case:
            self.assertRaises(
                AssertionError, general_health_message_bank_content, self._reminder(iteration_num=2),
                self._handler(), case)

    def test_multiple_relevant_messages(self):
        self._setup_fixture_type()
        self._setup_data_item('risk1', '1', 'message2')
        with create_test_case(self.domain_name, self.case_type, 'test-case', {'risk_profile': 'risk1'}) as case:
            self.assertRaises(
                AssertionError, general_health_message_bank_content, self._reminder(), self._handler(), case)

    def test_correct_message(self):
        self._setup_fixture_type()
        with create_test_case(self.domain_name, self.case_type, 'test-case', {'risk_profile': 'risk1'}) as case:
            self.assertEqual(
                general_health_message_bank_content(self._reminder(), self._handler(), case), 'message1')

    def test_message_bank_doesnt_exist_new(self):
        with create_test_case(self.domain_name, self.case_type, 'test-case') as case:
            with self.assertRaises(AssertionError) as e:
                self._get_current_event_messages(self._schedule_instance(case))

            self.assertIn('Lookup Table general_health not found', str(e.exception))

    def test_message_bank_doesnt_have_correct_properties_new(self):
        data_type = LookupTable(
            domain=self.domain_name,
            tag=self.fixture_name,
            fields=[],
            item_attributes=[]
        )
        data_type.save()
        with create_test_case(self.domain_name, self.case_type, 'test-case') as case:
            with self.assertRaises(AssertionError) as e:
                self._get_current_event_messages(self._schedule_instance(case))

            self.assertIn('must have', str(e.exception))

    def test_not_passing_case_new(self):
        self._setup_fixture_type()
        with create_test_case(self.domain_name, self.case_type, 'test-case', {'risk_profile': 'risk1'}) as case:
            schedule_instance = self._schedule_instance(case)
            schedule_instance.recipient_type = ScheduleInstance.RECIPIENT_TYPE_WEB_USER
            schedule_instance.recipient_id = self.user.get_id
            with self.assertRaises(AssertionError) as e:
                self._get_current_event_messages(schedule_instance)

            self.assertIn('must be a case', str(e.exception))

    def test_passing_case_without_risk_profile_new(self):
        self._setup_fixture_type()
        with create_test_case(self.domain_name, self.case_type, 'test-case') as case:
            with self.assertRaises(AssertionError) as e:
                self._get_current_event_messages(self._schedule_instance(case))

            self.assertIn('does not include risk_profile', str(e.exception))

    def test_no_relevant_message_invalid_risk_new(self):
        self._setup_fixture_type()
        with create_test_case(self.domain_name, self.case_type, 'test-case', {'risk_profile': 'risk2'}) as case:
            with self.assertRaises(AssertionError) as e:
                self._get_current_event_messages(self._schedule_instance(case))

            self.assertIn('No message for case', str(e.exception))

    def test_no_relevant_message_invalid_seq_num_new(self):
        self._setup_fixture_type()
        with create_test_case(self.domain_name, self.case_type, 'test-case', {'risk_profile': 'risk1'}) as case:
            with self.assertRaises(AssertionError) as e:
                self._get_current_event_messages(self._schedule_instance(case, iteration_num=2))

            self.assertIn('No message for case', str(e.exception))

    def test_multiple_relevant_messages_new(self):
        self._setup_fixture_type()
        self._setup_data_item('risk1', '1', 'message2')
        with create_test_case(self.domain_name, self.case_type, 'test-case', {'risk_profile': 'risk1'}) as case:
            with self.assertRaises(AssertionError) as e:
                self._get_current_event_messages(self._schedule_instance(case))

            self.assertIn('Multiple messages for case', str(e.exception))

    def test_correct_message_new(self):
        self._setup_fixture_type()
        with create_test_case(self.domain_name, self.case_type, 'test-case', {'risk_profile': 'risk1'}) as case:
            self.assertEqual(
                self._get_current_event_messages(self._schedule_instance(case)),
                ['message1']
            )
