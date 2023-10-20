import uuid
from datetime import time

from django.test import TestCase, override_settings

from casexml.apps.case.tests.util import create_case

from corehq.apps.casegroups.models import CommCareCaseGroup
from corehq.apps.custom_data_fields.models import (
    PROFILE_SLUG,
    CustomDataFieldsDefinition,
    CustomDataFieldsProfile,
    Field,
)
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.groups.models import Group
from corehq.apps.hqcase.utils import update_case
from corehq.apps.locations.models import SQLLocation
from corehq.apps.locations.tests.util import make_loc, setup_location_types
from corehq.apps.sms.models import PhoneNumber
from corehq.apps.users.models import CommCareUser, WebUser
from corehq.apps.users.util import normalize_username
from corehq.apps.users.views.mobile.custom_data_fields import UserFieldsView
from corehq.form_processor.models import CommCareCase
from corehq.form_processor.utils import is_commcarecase
from corehq.messaging.pillow import get_case_messaging_sync_pillow
from corehq.messaging.scheduling.models import (
    Content,
    SMSContent,
    TimedEvent,
    TimedSchedule,
)
from corehq.messaging.scheduling.scheduling_partitioned.models import (
    CaseScheduleInstanceMixin,
    CaseTimedScheduleInstance,
)
from corehq.messaging.scheduling.scheduling_partitioned.models import \
    ScheduleInstance as AbstractScheduleInstance
from corehq.messaging.scheduling.tests.util import delete_timed_schedules
from corehq.util.test_utils import (
    create_test_case,
    set_parent_case,
    unregistered_django_model,
)
from testapps.test_pillowtop.utils import process_pillow_changes


class SchedulingRecipientTest(TestCase):
    domain = 'scheduling-recipient-test'

    @classmethod
    def setUpClass(cls):
        super(SchedulingRecipientTest, cls).setUpClass()

        cls.domain_obj = create_domain(cls.domain)

        cls.location_types = setup_location_types(cls.domain, ['country', 'state', 'city'])
        cls.country_location = make_loc('usa', domain=cls.domain, type='country')
        cls.state_location = make_loc('ma', domain=cls.domain, type='state', parent=cls.country_location)
        cls.city_location = make_loc('boston', domain=cls.domain, type='city', parent=cls.state_location)

        cls.mobile_user = CommCareUser.create(cls.domain, 'mobile', 'abc', None, None)
        cls.mobile_user.set_location(cls.city_location)

        cls.mobile_user2 = CommCareUser.create(cls.domain, 'mobile2', 'abc', None, None)
        cls.mobile_user2.set_location(cls.state_location)

        cls.mobile_user3 = CommCareUser.create(cls.domain, 'mobile3', 'abc', None, None, user_data={
            'role': 'pharmacist',
        })
        cls.mobile_user3.save()

        cls.mobile_user4 = CommCareUser.create(cls.domain, 'mobile4', 'abc', None, None, user_data={
            'role': 'nurse',
        })
        cls.mobile_user4.save()

        cls.mobile_user5 = CommCareUser.create(cls.domain, 'mobile5', 'abc', None, None, user_data={
            'role': ['nurse', 'pharmacist'],
        })
        cls.mobile_user5.save()

        full_username = normalize_username('mobile', cls.domain)
        cls.full_mobile_user = CommCareUser.create(cls.domain, full_username, 'abc', None, None)

        cls.definition = CustomDataFieldsDefinition(domain=cls.domain, field_type=UserFieldsView.field_type)
        cls.definition.save()
        cls.definition.set_fields([
            Field(
                slug='role',
                label='Role',
            ),
        ])
        cls.definition.save()
        cls.profile = CustomDataFieldsProfile(
            name='nurse_profile',
            fields={'role': ['nurse']},
            definition=cls.definition,
        )
        cls.profile.save()
        cls.mobile_user6 = CommCareUser.create(cls.domain, 'mobile6', 'abc', None, None, user_data={
            PROFILE_SLUG: cls.profile.id,
        })
        cls.mobile_user5.save()

        cls.web_user = WebUser.create(cls.domain, 'web', 'abc', None, None)

        cls.web_user2 = WebUser.create(cls.domain, 'web2', 'abc', None, None, user_data={
            'role': 'nurse',
        })
        cls.web_user2.save()

        cls.group = Group(domain=cls.domain, users=[cls.mobile_user.get_id])
        cls.group.save()

        cls.group2 = Group(
            domain=cls.domain,
            users=[
                cls.mobile_user.get_id,
                cls.mobile_user3.get_id,
                cls.mobile_user4.get_id,
                cls.mobile_user5.get_id,
                cls.mobile_user6.get_id,
            ]
        )
        cls.group2.save()

        cls.case_group = CommCareCaseGroup(domain=cls.domain)
        cls.case_group.save()

        cls.process_pillow_changes = process_pillow_changes('DefaultChangeFeedPillow')
        cls.process_pillow_changes.add_pillow(get_case_messaging_sync_pillow())

    @classmethod
    def tearDownClass(cls):
        cls.domain_obj.delete()
        super(SchedulingRecipientTest, cls).tearDownClass()

    def tearDown(self):
        delete_timed_schedules(self.domain)
        PhoneNumber.objects.filter(domain=self.domain).delete()
        super(SchedulingRecipientTest, self).tearDown()

    def user_ids(self, users):
        return [user.get_id for user in users]

    def test_specific_case_recipient(self):
        with create_case(self.domain, 'person') as case:
            instance = ScheduleInstance(
                domain=self.domain,
                recipient_type=ScheduleInstance.RECIPIENT_TYPE_CASE,
                recipient_id=case.case_id,
            )
            self.assertEqual(instance.recipient.case_id, case.case_id)

        instance = ScheduleInstance(
            domain=self.domain,
            recipient_type=ScheduleInstance.RECIPIENT_TYPE_CASE,
            recipient_id='id-does-not-exist',
        )
        self.assertIsNone(instance.recipient)

    def test_specific_mobile_worker_recipient(self):
        instance = ScheduleInstance(
            domain=self.domain,
            recipient_type=ScheduleInstance.RECIPIENT_TYPE_MOBILE_WORKER,
            recipient_id=self.mobile_user.get_id,
        )
        self.assertTrue(isinstance(instance.recipient, CommCareUser))
        self.assertEqual(instance.recipient.get_id, self.mobile_user.get_id)

        instance = ScheduleInstance(
            domain=self.domain,
            recipient_type=ScheduleInstance.RECIPIENT_TYPE_MOBILE_WORKER,
            recipient_id=self.web_user.get_id,
        )
        self.assertIsNone(instance.recipient)

        instance = ScheduleInstance(
            domain=self.domain,
            recipient_type=ScheduleInstance.RECIPIENT_TYPE_MOBILE_WORKER,
            recipient_id='id-does-not-exist',
        )
        self.assertIsNone(instance.recipient)

    def test_specific_web_user_recipient(self):
        instance = ScheduleInstance(
            domain=self.domain,
            recipient_type=ScheduleInstance.RECIPIENT_TYPE_WEB_USER,
            recipient_id=self.web_user.get_id,
        )
        self.assertTrue(isinstance(instance.recipient, WebUser))
        self.assertEqual(instance.recipient.get_id, self.web_user.get_id)

        instance = ScheduleInstance(
            domain=self.domain,
            recipient_type=ScheduleInstance.RECIPIENT_TYPE_WEB_USER,
            recipient_id=self.mobile_user.get_id,
        )
        self.assertIsNone(instance.recipient)

        instance = ScheduleInstance(
            domain=self.domain,
            recipient_type=ScheduleInstance.RECIPIENT_TYPE_WEB_USER,
            recipient_id='id-does-not-exist',
        )
        self.assertIsNone(instance.recipient)

    def test_specific_case_group_recipient(self):
        instance = ScheduleInstance(
            domain=self.domain,
            recipient_type=ScheduleInstance.RECIPIENT_TYPE_CASE_GROUP,
            recipient_id=self.case_group.get_id,
        )
        self.assertTrue(isinstance(instance.recipient, CommCareCaseGroup))
        self.assertEqual(instance.recipient.get_id, self.case_group.get_id)

        instance = ScheduleInstance(
            domain=self.domain,
            recipient_type=ScheduleInstance.RECIPIENT_TYPE_CASE_GROUP,
            recipient_id='id-does-not-exist',
        )
        self.assertIsNone(instance.recipient)

    def test_specific_group_recipient(self):
        instance = ScheduleInstance(
            domain=self.domain,
            recipient_type=ScheduleInstance.RECIPIENT_TYPE_USER_GROUP,
            recipient_id=self.group.get_id,
        )
        self.assertTrue(isinstance(instance.recipient, Group))
        self.assertEqual(instance.recipient.get_id, self.group.get_id)

        instance = ScheduleInstance(
            domain=self.domain,
            recipient_type=ScheduleInstance.RECIPIENT_TYPE_USER_GROUP,
            recipient_id='id-does-not-exist',
        )
        self.assertIsNone(instance.recipient)

    def test_specific_location_recipient(self):
        instance = ScheduleInstance(
            domain=self.domain,
            recipient_type=ScheduleInstance.RECIPIENT_TYPE_LOCATION,
            recipient_id=self.city_location.location_id,
        )
        self.assertTrue(isinstance(instance.recipient, SQLLocation))
        self.assertEqual(instance.recipient.location_id, self.city_location.location_id)

        instance = ScheduleInstance(
            domain=self.domain,
            recipient_type=ScheduleInstance.RECIPIENT_TYPE_LOCATION,
            recipient_id='id-does-not-exist',
        )
        self.assertIsNone(instance.recipient)

    def test_case_recipient(self):
        with create_case(self.domain, 'person') as case:
            instance = CaseTimedScheduleInstance(domain=self.domain, case_id=case.case_id, recipient_type='Self')
            self.assertTrue(is_commcarecase(instance.recipient))
            self.assertEqual(instance.recipient.case_id, case.case_id)

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

    def test_last_submitting_user_recipient(self):
        with create_test_case(self.domain, 'person', 'Joe', user_id=self.mobile_user.get_id) as case:
            instance = CaseTimedScheduleInstance(domain=self.domain, case_id=case.case_id,
                recipient_type=CaseScheduleInstanceMixin.RECIPIENT_TYPE_LAST_SUBMITTING_USER)
            self.assertTrue(isinstance(instance.recipient, CommCareUser))
            self.assertEqual(instance.recipient.get_id, self.mobile_user.get_id)

        with create_test_case(self.domain, 'person', 'Joe', user_id=self.web_user.get_id) as case:
            instance = CaseTimedScheduleInstance(domain=self.domain, case_id=case.case_id,
                recipient_type=CaseScheduleInstanceMixin.RECIPIENT_TYPE_LAST_SUBMITTING_USER)
            self.assertTrue(isinstance(instance.recipient, WebUser))
            self.assertEqual(instance.recipient.get_id, self.web_user.get_id)

        with create_test_case(self.domain, 'person', 'Joe', user_id='system') as case:
            instance = CaseTimedScheduleInstance(domain=self.domain, case_id=case.case_id,
                recipient_type=CaseScheduleInstanceMixin.RECIPIENT_TYPE_LAST_SUBMITTING_USER)
            self.assertIsNone(instance.recipient)

    def test_parent_case_recipient(self):
        with create_case(self.domain, 'person') as child, create_case(self.domain, 'person') as parent:
            instance = CaseTimedScheduleInstance(domain=self.domain, case_id=child.case_id,
                recipient_type=CaseScheduleInstanceMixin.RECIPIENT_TYPE_PARENT_CASE)
            self.assertIsNone(instance.recipient)

            set_parent_case(self.domain, child, parent, relationship='child', identifier='parent')
            instance = CaseTimedScheduleInstance(domain=self.domain, case_id=child.case_id,
                recipient_type=CaseScheduleInstanceMixin.RECIPIENT_TYPE_PARENT_CASE)
            self.assertEqual(instance.recipient.case_id, parent.case_id)

    def test_child_case_recipient(self):
        with create_case(self.domain, 'person') as child_1, \
                create_case(self.domain, 'person') as child_2, \
                create_case(self.domain, 'person') as parent:

            instance = CaseTimedScheduleInstance(domain=self.domain, case_id=parent.case_id,
                recipient_type=CaseScheduleInstanceMixin.RECIPIENT_TYPE_ALL_CHILD_CASES)
            self.assertIsInstance(instance.recipient, list)
            self.assertEqual(len(instance.recipient), 0)

            set_parent_case(self.domain, child_1, parent, relationship='child', identifier='parent')
            set_parent_case(self.domain, child_2, parent, relationship='child', identifier='parent')

            instance = CaseTimedScheduleInstance(domain=self.domain, case_id=parent.case_id,
                recipient_type=CaseScheduleInstanceMixin.RECIPIENT_TYPE_ALL_CHILD_CASES)

            self.assertIsInstance(instance.recipient, list)
            self.assertEqual(len(instance.recipient), 2)
            self.assertItemsEqual([c.case_id for c in instance.recipient], [child_1.case_id, child_2.case_id])

    def test_host_case_owner_location(self):
        with create_test_case(self.domain, 'test-extension-case', 'name') as extension_case:
            with create_test_case(self.domain, 'test-host-case', 'name') as host_case:

                self.update_case_and_process_change(self.domain, host_case.case_id,
                    case_properties={'owner_id': self.city_location.location_id})
                set_parent_case(self.domain, extension_case, host_case, relationship='extension')

                # Test the recipient is returned correctly
                instance = CaseTimedScheduleInstance(
                    domain=self.domain,
                    case_id=extension_case.case_id,
                    recipient_type=CaseScheduleInstanceMixin.RECIPIENT_TYPE_CUSTOM,
                    recipient_id='HOST_CASE_OWNER_LOCATION',
                )
                self.assertIsInstance(instance.recipient, SQLLocation)
                self.assertEqual(instance.recipient.location_id, self.city_location.location_id)

                # Test location that does not exist
                self.update_case_and_process_change(
                    self.domain,
                    host_case.case_id,
                    case_properties={'owner_id': 'does-not-exist'}
                )
                instance = CaseTimedScheduleInstance(
                    domain=self.domain,
                    case_id=extension_case.case_id,
                    recipient_type=CaseScheduleInstanceMixin.RECIPIENT_TYPE_CUSTOM,
                    recipient_id='HOST_CASE_OWNER_LOCATION',
                )
                self.assertIsNone(instance.recipient)

                # Test on a case that is not an extension case
                instance = CaseTimedScheduleInstance(
                    domain=self.domain,
                    case_id=host_case.case_id,
                    recipient_type=CaseScheduleInstanceMixin.RECIPIENT_TYPE_CUSTOM,
                    recipient_id='HOST_CASE_OWNER_LOCATION',
                )
                self.assertIsNone(instance.recipient)

                # Test with case id that doesn't exist
                instance = CaseTimedScheduleInstance(
                    domain=self.domain,
                    case_id='does-not-exist',
                    recipient_type=CaseScheduleInstanceMixin.RECIPIENT_TYPE_CUSTOM,
                    recipient_id='HOST_CASE_OWNER_LOCATION',
                )
                self.assertIsNone(instance.recipient)

    def test_host_case_owner_location_parent(self):
        with create_test_case(self.domain, 'test-extension-case', 'name') as extension_case:
            with create_test_case(self.domain, 'test-host-case', 'name') as host_case:

                self.update_case_and_process_change(self.domain, host_case.case_id,
                    case_properties={'owner_id': self.city_location.location_id})
                set_parent_case(self.domain, extension_case, host_case, relationship='extension')

                # Test the recipient is returned correctly
                instance = CaseTimedScheduleInstance(
                    domain=self.domain,
                    case_id=extension_case.case_id,
                    recipient_type=CaseScheduleInstanceMixin.RECIPIENT_TYPE_CUSTOM,
                    recipient_id='HOST_CASE_OWNER_LOCATION_PARENT',
                )
                self.assertIsInstance(instance.recipient, SQLLocation)
                self.assertEqual(instance.recipient.location_id, self.state_location.location_id)

                # Test no parent location
                self.update_case_and_process_change(self.domain, host_case.case_id,
                    case_properties={'owner_id': self.country_location.location_id})
                instance = CaseTimedScheduleInstance(
                    domain=self.domain,
                    case_id=extension_case.case_id,
                    recipient_type=CaseScheduleInstanceMixin.RECIPIENT_TYPE_CUSTOM,
                    recipient_id='HOST_CASE_OWNER_LOCATION_PARENT',
                )
                self.assertIsNone(instance.recipient)

                # Test location that does not exist
                self.update_case_and_process_change(
                    self.domain,
                    host_case.case_id,
                    case_properties={'owner_id': 'does-not-exist'}
                )
                instance = CaseTimedScheduleInstance(
                    domain=self.domain,
                    case_id=extension_case.case_id,
                    recipient_type=CaseScheduleInstanceMixin.RECIPIENT_TYPE_CUSTOM,
                    recipient_id='HOST_CASE_OWNER_LOCATION_PARENT',
                )
                self.assertIsNone(instance.recipient)

                # Test on a case that is not an extension case
                instance = CaseTimedScheduleInstance(
                    domain=self.domain,
                    case_id=host_case.case_id,
                    recipient_type=CaseScheduleInstanceMixin.RECIPIENT_TYPE_CUSTOM,
                    recipient_id='HOST_CASE_OWNER_LOCATION_PARENT',
                )
                self.assertIsNone(instance.recipient)

                # Test with case id that doesn't exist
                instance = CaseTimedScheduleInstance(
                    domain=self.domain,
                    case_id='does-not-exist',
                    recipient_type=CaseScheduleInstanceMixin.RECIPIENT_TYPE_CUSTOM,
                    recipient_id='HOST_CASE_OWNER_LOCATION_PARENT',
                )
                self.assertIsNone(instance.recipient)

    def test_expand_location_recipients_without_descendants(self):
        schedule = TimedSchedule.create_simple_daily_schedule(
            self.domain,
            TimedEvent(time=time(9, 0)),
            SMSContent(message={'en': 'Hello'})
        )
        schedule.include_descendant_locations = False
        schedule.save()

        instance = CaseTimedScheduleInstance(
            domain=self.domain,
            timed_schedule_id=schedule.schedule_id,
            recipient_type='Location',
            recipient_id=self.country_location.location_id
        )
        self.assertEqual(
            list(instance.expand_recipients()),
            []
        )

        instance = CaseTimedScheduleInstance(
            domain=self.domain,
            timed_schedule_id=schedule.schedule_id,
            recipient_type='Location',
            recipient_id=self.state_location.location_id
        )
        self.assertEqual(
            self.user_ids(instance.expand_recipients()),
            [self.mobile_user2.get_id]
        )

    def test_expand_location_recipients_with_descendants(self):
        schedule = TimedSchedule.create_simple_daily_schedule(
            self.domain,
            TimedEvent(time=time(9, 0)),
            SMSContent(message={'en': 'Hello'})
        )
        schedule.include_descendant_locations = True
        schedule.save()

        instance = CaseTimedScheduleInstance(
            domain=self.domain,
            timed_schedule_id=schedule.schedule_id,
            recipient_type='Location',
            recipient_id=self.state_location.location_id
        )
        self.assertItemsEqual(
            self.user_ids(instance.expand_recipients()),
            [self.mobile_user.get_id, self.mobile_user2.get_id]
        )

    def test_expand_location_recipients_with_location_type_filter(self):
        schedule = TimedSchedule.create_simple_daily_schedule(
            self.domain,
            TimedEvent(time=time(9, 0)),
            SMSContent(message={'en': 'Hello'})
        )
        schedule.include_descendant_locations = True
        schedule.location_type_filter = [self.city_location.location_type_id]
        schedule.save()

        instance = CaseTimedScheduleInstance(
            domain=self.domain,
            timed_schedule_id=schedule.schedule_id,
            recipient_type='Location',
            recipient_id=self.country_location.location_id
        )
        self.assertItemsEqual(
            self.user_ids(instance.expand_recipients()),
            [self.mobile_user.get_id]
        )

    def test_expand_group_recipients(self):
        schedule = TimedSchedule.create_simple_daily_schedule(
            self.domain,
            TimedEvent(time=time(9, 0)),
            SMSContent(message={'en': 'Hello'})
        )
        instance = CaseTimedScheduleInstance(
            domain=self.domain,
            timed_schedule_id=schedule.schedule_id,
            recipient_type='Group',
            recipient_id=self.group.get_id
        )
        self.assertEqual(
            self.user_ids(instance.expand_recipients()),
            [self.mobile_user.get_id]
        )

    def test_mobile_worker_recipients_with_user_data_filter(self):
        schedule = TimedSchedule.create_simple_daily_schedule(
            self.domain,
            TimedEvent(time=time(9, 0)),
            SMSContent(message={'en': 'Hello'})
        )
        schedule.user_data_filter = {'role': ['nurse']}
        schedule.save()

        instance = CaseTimedScheduleInstance(
            domain=self.domain,
            timed_schedule_id=schedule.schedule_id,
            recipient_type='Group',
            recipient_id=self.group2.get_id
        )
        self.assertEqual(
            self.user_ids(instance.expand_recipients()),
            [self.mobile_user4.get_id, self.mobile_user5.get_id, self.mobile_user6.get_id]
        )

    def test_web_user_recipient_with_user_data_filter(self):
        schedule = TimedSchedule.create_simple_daily_schedule(
            self.domain,
            TimedEvent(time=time(9, 0)),
            SMSContent(message={'en': 'Hello'})
        )
        schedule.user_data_filter = {'role': ['nurse']}
        schedule.save()

        instance = CaseTimedScheduleInstance(
            domain=self.domain,
            timed_schedule_id=schedule.schedule_id,
            recipient_type=ScheduleInstance.RECIPIENT_TYPE_WEB_USER,
            recipient_id=self.web_user.get_id,
        )
        self.assertEqual(list(instance.expand_recipients()), [])

        instance = CaseTimedScheduleInstance(
            domain=self.domain,
            timed_schedule_id=schedule.schedule_id,
            recipient_type=ScheduleInstance.RECIPIENT_TYPE_WEB_USER,
            recipient_id=self.web_user2.get_id,
        )
        recipients = list(instance.expand_recipients())
        self.assertEqual(len(recipients), 1)
        self.assertIsInstance(recipients[0], WebUser)
        self.assertEqual(recipients[0].get_id, self.web_user2.get_id)

    def test_case_group_recipient_with_user_data_filter(self):
        # The user data filter should have no effect here because all
        # the recipients are cases.

        schedule = TimedSchedule.create_simple_daily_schedule(
            self.domain,
            TimedEvent(time=time(9, 0)),
            SMSContent(message={'en': 'Hello'})
        )
        schedule.user_data_filter = {'role': ['nurse']}
        schedule.save()

        with create_case(self.domain, 'person') as case:
            case_group = CommCareCaseGroup(domain=self.domain, cases=[case.case_id])
            case_group.save()
            self.addCleanup(case_group.delete)

            instance = CaseTimedScheduleInstance(
                domain=self.domain,
                timed_schedule_id=schedule.schedule_id,
                recipient_type=ScheduleInstance.RECIPIENT_TYPE_CASE_GROUP,
                recipient_id=case_group.get_id,
            )
            recipients = list(instance.expand_recipients())
            self.assertEqual(len(recipients), 1)
            self.assertEqual(recipients[0].case_id, case.case_id)

    def test_username_case_property_recipient(self):
        # test valid username
        with create_case(
                self.domain,
                'person',
                owner_id=self.city_location.location_id,
                update={'recipient': 'mobile'}
        ) as case:
            instance = CaseTimedScheduleInstance(
                domain=self.domain,
                case_id=case.case_id,
                recipient_type=CaseScheduleInstanceMixin.RECIPIENT_TYPE_CASE_PROPERTY_USER,
                recipient_id='recipient'
            )
            self.assertEqual(instance.recipient.get_id, self.full_mobile_user.get_id)

        # test invalid username
        with create_case(
                self.domain,
                'person',
                owner_id=self.city_location.location_id,
                update={'recipient': 'mobile10'}
        ) as case:
            instance = CaseTimedScheduleInstance(
                domain=self.domain,
                case_id=case.case_id,
                recipient_type=CaseScheduleInstanceMixin.RECIPIENT_TYPE_CASE_PROPERTY_USER,
                recipient_id='recipient'
            )
            self.assertIsNone(instance.recipient)

        # test no username
        with create_case(
                self.domain,
                'person',
                owner_id=self.city_location.location_id
        ) as case:
            instance = CaseTimedScheduleInstance(
                domain=self.domain,
                case_id=case.case_id,
                recipient_type=CaseScheduleInstanceMixin.RECIPIENT_TYPE_CASE_PROPERTY_USER,
                recipient_id='recipient'
            )
            self.assertIsNone(instance.recipient)

    def test_email_case_property_recipient(self):
        with create_case(
                self.domain,
                'person',
                owner_id=self.city_location.location_id,
                update={'recipient': 'fake@mail.com', 'language_code': 'en', 'time_zone': 'sast'}
        ) as case:
            instance = CaseTimedScheduleInstance(
                domain=self.domain,
                case_id=case.case_id,
                recipient_type=CaseScheduleInstanceMixin.RECIPIENT_TYPE_CASE_PROPERTY_EMAIL,
                recipient_id='recipient'
            )
            self.assertEqual(instance.recipient.get_email(), 'fake@mail.com')
            self.assertEqual(instance.recipient.get_language_code(), 'en')
            self.assertEqual(instance.recipient.get_time_zone(), 'sast')

        # test that cases without the properties don't fail
        with create_case(
                self.domain,
                'person',
                owner_id=self.city_location.location_id
        ) as case:
            instance = CaseTimedScheduleInstance(
                domain=self.domain,
                case_id=case.case_id,
                recipient_type=CaseScheduleInstanceMixin.RECIPIENT_TYPE_CASE_PROPERTY_EMAIL,
                recipient_id='recipient'
            )
            self.assertIsNone(instance.recipient.get_email())
            self.assertIsNone(instance.recipient.get_language_code())
            self.assertIsNone(instance.recipient.get_time_zone())

    def create_usercase(self, user):
        with self.process_pillow_changes:
            create_case_kwargs = {
                'external_id': user.get_id,
                'update': {'hq_user_id': user.get_id},
            }
            return create_case(self.domain, 'commcare-user', **create_case_kwargs)

    def update_case_and_process_change(self, *args, **kwargs):
        with self.process_pillow_changes:
            return update_case(*args, **kwargs)

    def assertPhoneEntryCount(self, count, only_count_two_way=False):
        qs = PhoneNumber.objects.filter(domain=self.domain)
        if only_count_two_way:
            qs = qs.filter(is_two_way=True)
        self.assertEqual(qs.count(), count)

    def assertTwoWayEntry(self, entry, expected_phone_number):
        self.assertTrue(isinstance(entry, PhoneNumber))
        self.assertEqual(entry.phone_number, expected_phone_number)
        self.assertTrue(entry.is_two_way)

    def test_one_way_numbers(self):
        user1 = CommCareUser.create(self.domain, uuid.uuid4().hex, 'abc', None, None)
        user2 = CommCareUser.create(self.domain, uuid.uuid4().hex, 'abc', None, None)
        user3 = CommCareUser.create(self.domain, uuid.uuid4().hex, 'abc', None, None)
        self.addCleanup(user1.delete, self.domain, deleted_by=None)
        self.addCleanup(user2.delete, self.domain, deleted_by=None)
        self.addCleanup(user3.delete, self.domain, deleted_by=None)

        self.assertIsNone(user1.memoized_usercase)
        self.assertIsNone(Content.get_two_way_entry_or_phone_number(user1))

        with self.create_usercase(user2) as case:
            self.assertIsNotNone(user2.memoized_usercase)
            self.assertIsNone(Content.get_two_way_entry_or_phone_number(user2))
            self.assertIsNone(Content.get_two_way_entry_or_phone_number(case))

        with self.create_usercase(user3) as case:
            # If the user has no number, the user case's number is used
            self.update_case_and_process_change(
                self.domain,
                case.case_id,
                case_properties={'contact_phone_number': '12345678'}
            )
            case = CommCareCase.objects.get_case(case.case_id, self.domain)
            self.assertPhoneEntryCount(1)
            self.assertPhoneEntryCount(0, only_count_two_way=True)
            self.assertIsNotNone(user3.memoized_usercase)
            self.assertEqual(Content.get_two_way_entry_or_phone_number(user3), '12345678')

            # If the user has a number, it is used before the user case's number
            user3.add_phone_number('87654321')
            user3.save()
            self.assertPhoneEntryCount(2)
            self.assertPhoneEntryCount(0, only_count_two_way=True)
            self.assertEqual(Content.get_two_way_entry_or_phone_number(user3), '87654321')

            # Referencing the case directly uses the case's phone number
            self.assertEqual(Content.get_two_way_entry_or_phone_number(case), '12345678')

    def test_ignoring_entries(self):
        with create_case(self.domain, 'person') as case:
            self.update_case_and_process_change(self.domain, case.case_id,
                case_properties={'contact_phone_number': '12345', 'contact_phone_number_is_verified': '1'})

            self.assertPhoneEntryCount(1)
            self.assertPhoneEntryCount(1, only_count_two_way=True)

            with override_settings(USE_PHONE_ENTRIES=False):
                self.update_case_and_process_change(
                    self.domain,
                    case.case_id,
                    case_properties={'contact_phone_number': '23456'}
                )
                case = CommCareCase.objects.get_case(case.case_id, self.domain)

                self.assertPhoneEntryCount(1)
                self.assertPhoneEntryCount(1, only_count_two_way=True)
                self.assertTwoWayEntry(PhoneNumber.objects.get(owner_id=case.case_id), '12345')
                self.assertEqual(Content.get_two_way_entry_or_phone_number(case), '23456')

    def test_two_way_numbers(self):
        user1 = CommCareUser.create(self.domain, uuid.uuid4().hex, 'abc', None, None)
        user2 = CommCareUser.create(self.domain, uuid.uuid4().hex, 'abc', None, None)
        user3 = CommCareUser.create(self.domain, uuid.uuid4().hex, 'abc', None, None)
        self.addCleanup(user1.delete, self.domain, deleted_by=None)
        self.addCleanup(user2.delete, self.domain, deleted_by=None)
        self.addCleanup(user3.delete, self.domain, deleted_by=None)

        self.assertIsNone(user1.memoized_usercase)
        self.assertIsNone(Content.get_two_way_entry_or_phone_number(user1))

        with self.create_usercase(user2) as case:
            self.assertIsNotNone(user2.memoized_usercase)
            self.assertIsNone(Content.get_two_way_entry_or_phone_number(user2))
            self.assertIsNone(Content.get_two_way_entry_or_phone_number(case))

        with self.create_usercase(user3) as case:
            # If the user has no number, the user case's number is used
            self.update_case_and_process_change(self.domain, case.case_id,
                                                case_properties={'contact_phone_number': '12345678',
                                                                 'contact_phone_number_is_verified': '1'})
            case = CommCareCase.objects.get_case(case.case_id, self.domain)
            self.assertPhoneEntryCount(1)
            self.assertPhoneEntryCount(1, only_count_two_way=True)
            self.assertIsNotNone(user3.memoized_usercase)
            self.assertTwoWayEntry(Content.get_two_way_entry_or_phone_number(user3), '12345678')

            # If the user has a number, it is used before the user case's number
            user3.add_phone_number('87654321')
            user3.save()
            PhoneNumber.objects.get(phone_number='87654321').set_two_way()
            self.assertPhoneEntryCount(2)
            self.assertPhoneEntryCount(2, only_count_two_way=True)
            self.assertTwoWayEntry(Content.get_two_way_entry_or_phone_number(user3), '87654321')

            # Referencing the case directly uses the case's phone number
            self.assertTwoWayEntry(Content.get_two_way_entry_or_phone_number(case), '12345678')

    def test_not_using_phone_entries(self):
        with override_settings(USE_PHONE_ENTRIES=False):
            user1 = CommCareUser.create(self.domain, uuid.uuid4().hex, 'abc', None, None)
            user2 = CommCareUser.create(self.domain, uuid.uuid4().hex, 'abc', None, None)
            user3 = CommCareUser.create(self.domain, uuid.uuid4().hex, 'abc', None, None)
            self.addCleanup(user1.delete, self.domain, deleted_by=None)
            self.addCleanup(user2.delete, self.domain, deleted_by=None)
            self.addCleanup(user3.delete, self.domain, deleted_by=None)

            self.assertIsNone(user1.memoized_usercase)
            self.assertIsNone(Content.get_two_way_entry_or_phone_number(user1))

            with self.create_usercase(user2) as case:
                self.assertIsNotNone(user2.memoized_usercase)
                self.assertIsNone(Content.get_two_way_entry_or_phone_number(user2))
                self.assertIsNone(Content.get_two_way_entry_or_phone_number(case))

            with self.create_usercase(user3) as case:
                # If the user has no number, the user case's number is used
                self.update_case_and_process_change(
                    self.domain,
                    case.case_id,
                    case_properties={'contact_phone_number': '12345678'}
                )
                case = CommCareCase.objects.get_case(case.case_id, self.domain)
                self.assertPhoneEntryCount(0)
                self.assertIsNotNone(user3.memoized_usercase)
                self.assertEqual(Content.get_two_way_entry_or_phone_number(user3), '12345678')

                # If the user has a number, it is used before the user case's number
                user3.add_phone_number('87654321')
                user3.save()
                self.assertPhoneEntryCount(0)
                self.assertEqual(Content.get_two_way_entry_or_phone_number(user3), '87654321')

                # Referencing the case directly uses the case's phone number
                self.assertEqual(Content.get_two_way_entry_or_phone_number(case), '12345678')

    def test_phone_number_preference(self):
        user = CommCareUser.create(self.domain, uuid.uuid4().hex, 'abc', None, None)
        self.addCleanup(user.delete, self.domain, deleted_by=None)

        user.add_phone_number('12345')
        user.add_phone_number('23456')
        user.add_phone_number('34567')
        user.save()

        self.assertPhoneEntryCount(3)
        self.assertPhoneEntryCount(0, only_count_two_way=True)
        self.assertEqual(Content.get_two_way_entry_or_phone_number(user), '12345')

        PhoneNumber.objects.get(phone_number='23456').set_two_way()
        self.assertPhoneEntryCount(3)
        self.assertPhoneEntryCount(1, only_count_two_way=True)
        self.assertTwoWayEntry(Content.get_two_way_entry_or_phone_number(user), '23456')


@unregistered_django_model
class ScheduleInstance(AbstractScheduleInstance):
    pass
