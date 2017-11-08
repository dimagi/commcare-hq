from __future__ import absolute_import
from collections import namedtuple
import uuid
from django.test import TestCase, override_settings

from corehq.apps.domain.models import Domain
from corehq.apps.fixtures.models import (
    FixtureDataType, FixtureTypeField, FixtureDataItem, FieldList, FixtureItemField
)
from corehq.apps.users.models import WebUser
from corehq.util.test_utils import create_test_case
from custom.ucla.api import general_health_message_bank_content

Reminder = namedtuple('Reminder', ['domain', 'schedule_iteration_num', 'current_event_sequence_num'])
Handler = namedtuple('Handler', ['events'])


@override_settings(TESTS_SHOULD_USE_SQL_BACKEND=True)
class TestUCLACustomHandler(TestCase):
    domain_name = uuid.uuid4().hex
    case_type = 'ucla-reminder'
    fixture_name = 'general_health'

    @classmethod
    def setUpClass(cls):
        super(TestUCLACustomHandler, cls).setUpClass()
        cls.domain = Domain.get_or_create_with_name(cls.domain_name, is_active=True)
        email = 'dimagi@dimagi.com'
        cls.user = WebUser.create(cls.domain_name, email, '***', email=email)
        cls.user.save()

    @classmethod
    def tearDownClass(cls):
        cls.user.delete()
        cls.domain.delete()
        super(TestUCLACustomHandler, cls).tearDownClass()

    def _reminder(self, iteration_num=1):
        return Reminder(
            domain=self.domain_name,
            schedule_iteration_num=iteration_num,
            current_event_sequence_num=0,
        )

    def _handler(self):
        return Handler(events=[None])

    def _setup_fixture_type(self):
        self.data_type = FixtureDataType(
            domain=self.domain_name,
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
            domain=self.domain_name,
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

    def test_message_bank_doesnt_exist(self):
        with create_test_case(self.domain_name, self.case_type, 'test-case') as case:
            self.assertRaises(
                AssertionError, general_health_message_bank_content, self._reminder(), self._handler(), case)

    def test_message_bank_doesnt_have_correct_properties(self):
        data_type = FixtureDataType(
            domain=self.domain_name,
            tag=self.fixture_name,
            fields=[],
            item_attributes=[]
        )
        data_type.save()
        self.addCleanup(data_type.delete)
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
