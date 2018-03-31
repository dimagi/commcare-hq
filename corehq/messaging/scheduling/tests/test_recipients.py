from __future__ import absolute_import
from __future__ import unicode_literals
import uuid
from django.test import TestCase
from corehq.apps.data_interfaces.tests.util import create_case
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.hqcase.utils import update_case
from corehq.apps.groups.models import Group
from corehq.apps.locations.models import SQLLocation
from corehq.apps.locations.tests.util import make_loc, setup_location_types
from corehq.apps.users.models import CommCareUser, WebUser
from corehq.form_processor.tests.utils import run_with_all_backends
from corehq.form_processor.utils import is_commcarecase
from corehq.messaging.scheduling.models import TimedSchedule, TimedEvent, SMSContent, Content
from corehq.messaging.scheduling.scheduling_partitioned.models import CaseTimedScheduleInstance
from corehq.messaging.scheduling.tests.util import delete_timed_schedules
from datetime import time


class SchedulingRecipientTest(TestCase):
    domain = 'scheduling-recipient-test'

    @classmethod
    def setUpClass(cls):
        super(SchedulingRecipientTest, cls).setUpClass()

        cls.domain_obj = create_domain(cls.domain)

        cls.location_types = setup_location_types(cls.domain, ['country', 'state', 'city'])
        cls.state_location = make_loc('ma', domain=cls.domain, type='state')
        cls.city_location = make_loc('boston', domain=cls.domain, type='city', parent=cls.state_location)

        cls.mobile_user = CommCareUser.create(cls.domain, 'mobile', 'abc')
        cls.mobile_user.set_location(cls.city_location)

        cls.web_user = WebUser.create(cls.domain, 'web', 'abc')

        cls.group = Group(domain=cls.domain, users=[cls.mobile_user.get_id])
        cls.group.save()

    @classmethod
    def tearDownClass(cls):
        cls.domain_obj.delete()
        super(SchedulingRecipientTest, cls).tearDownClass()

    def tearDown(self):
        delete_timed_schedules(self.domain)

    def user_ids(self, users):
        return [user.get_id for user in users]

    @run_with_all_backends
    def test_case_recipient(self):
        with create_case(self.domain, 'person') as case:
            instance = CaseTimedScheduleInstance(domain=self.domain, case_id=case.case_id, recipient_type='Self')
            self.assertTrue(is_commcarecase(instance.recipient))
            self.assertEqual(instance.recipient.case_id, case.case_id)

    @run_with_all_backends
    def test_owner_recipient(self):
        with create_case(self.domain, 'person', owner_id=self.city_location.location_id) as case:
            instance = CaseTimedScheduleInstance(domain=self.domain, case_id=case.case_id, recipient_type='Owner')
            self.assertTrue(isinstance(instance.recipient, SQLLocation))
            self.assertEqual(instance.recipient.location_id, self.city_location.location_id)

        with create_case(self.domain, 'person', owner_id=self.group.get_id) as case:
            instance = CaseTimedScheduleInstance(domain=self.domain, case_id=case.case_id, recipient_type='Owner')
            self.assertTrue(isinstance(instance.recipient, Group))
            self.assertEqual(instance.recipient.get_id, self.group.get_id)

        with create_case(self.domain, 'person', owner_id=self.mobile_user.get_id) as case:
            instance = CaseTimedScheduleInstance(domain=self.domain, case_id=case.case_id, recipient_type='Owner')
            self.assertTrue(isinstance(instance.recipient, CommCareUser))
            self.assertEqual(instance.recipient.get_id, self.mobile_user.get_id)

        with create_case(self.domain, 'person', owner_id=self.web_user.get_id) as case:
            instance = CaseTimedScheduleInstance(domain=self.domain, case_id=case.case_id, recipient_type='Owner')
            self.assertTrue(isinstance(instance.recipient, WebUser))
            self.assertEqual(instance.recipient.get_id, self.web_user.get_id)

        with create_case(self.domain, 'person') as case:
            instance = CaseTimedScheduleInstance(domain=self.domain, case_id=case.case_id, recipient_type='Owner')
            self.assertIsNone(instance.recipient)

    def test_expand_location_recipients(self):
        schedule_without_descendants = TimedSchedule.create_simple_daily_schedule(
            self.domain,
            TimedEvent(time=time(9, 0)),
            SMSContent(message={'en': 'Hello'})
        )
        schedule_without_descendants.include_descendant_locations = False
        schedule_without_descendants.save()

        schedule_with_descendants = TimedSchedule.create_simple_daily_schedule(
            self.domain,
            TimedEvent(time=time(9, 0)),
            SMSContent(message={'en': 'Hello'})
        )
        schedule_with_descendants.include_descendant_locations = True
        schedule_with_descendants.save()

        instance = CaseTimedScheduleInstance(
            domain=self.domain,
            timed_schedule_id=schedule_without_descendants.schedule_id,
            recipient_type='Location',
            recipient_id=self.city_location.location_id
        )
        self.assertEqual(
            self.user_ids(instance.expand_recipients()),
            [self.mobile_user.get_id]
        )

        instance = CaseTimedScheduleInstance(
            domain=self.domain,
            timed_schedule_id=schedule_without_descendants.schedule_id,
            recipient_type='Location',
            recipient_id=self.state_location.location_id
        )
        self.assertEqual(
            list(instance.expand_recipients()),
            []
        )

        instance = CaseTimedScheduleInstance(
            domain=self.domain,
            timed_schedule_id=schedule_with_descendants.schedule_id,
            recipient_type='Location',
            recipient_id=self.state_location.location_id
        )
        self.assertEqual(
            self.user_ids(instance.expand_recipients()),
            [self.mobile_user.get_id]
        )

    def test_expand_group_recipients(self):
        instance = CaseTimedScheduleInstance(domain=self.domain, recipient_type='Group',
            recipient_id=self.group.get_id)
        self.assertEqual(
            self.user_ids(instance.expand_recipients()),
            [self.mobile_user.get_id]
        )

    def create_user_case(self, user):
        create_case_kwargs = {
            'external_id': user.get_id,
            'update': {'hq_user_id': user.get_id},
        }
        return create_case(self.domain, 'commcare-user', **create_case_kwargs)

    @run_with_all_backends
    def test_user_case_phone_number(self):
        user1 = CommCareUser.create(self.domain, uuid.uuid4().hex, 'abc')
        user2 = CommCareUser.create(self.domain, uuid.uuid4().hex, 'abc')
        user3 = CommCareUser.create(self.domain, uuid.uuid4().hex, 'abc')
        self.addCleanup(user1.delete)
        self.addCleanup(user2.delete)
        self.addCleanup(user3.delete)

        self.assertIsNone(user1.memoized_usercase)
        self.assertIsNone(Content.get_one_way_phone_number(user1))

        with self.create_user_case(user2) as case:
            self.assertIsNotNone(user2.memoized_usercase)
            self.assertIsNone(Content.get_one_way_phone_number(user2))

        with self.create_user_case(user3) as case:
            update_case(self.domain, case.case_id, case_properties={'contact_phone_number': '12345678'})
            self.assertIsNotNone(user3.memoized_usercase)
            self.assertEqual(Content.get_one_way_phone_number(user3), '12345678')

            user3.add_phone_number('87654321')
            self.assertEqual(Content.get_one_way_phone_number(user3), '87654321')
