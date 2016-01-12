from django.test import TestCase
from casexml.apps.case.sharedmodels import CommCareCaseIndex
from corehq.apps.accounting.models import SoftwarePlanEdition
from corehq.apps.accounting.tests.base_tests import BaseAccountingTest
from corehq.apps.accounting.tests.utils import DomainSubscriptionMixin
from corehq.apps.reminders.models import *
from corehq.apps.reminders.event_handlers import get_message_template_params
from corehq.apps.users.models import CommCareUser
from corehq.apps.sms.models import CallLog, ExpectedCallbackEventLog, CALLBACK_RECEIVED, CALLBACK_PENDING, CALLBACK_MISSED
from corehq.apps.sms.mixin import BackendMapping
from corehq.messaging.smsbackends.test.models import TestSMSBackend
from dimagi.utils.parsing import json_format_datetime
from dimagi.utils.couch import LOCK_EXPIRATION
from corehq.apps.domain.models import Domain
from corehq.apps.reminders.tests.test_util import *


class BaseReminderTestCase(BaseAccountingTest, DomainSubscriptionMixin):
    def setUp(self):
        super(BaseReminderTestCase, self).setUp()
        self.domain_obj = Domain(name="test")
        self.domain_obj.save()
        # Prevent resource conflict
        self.domain_obj = Domain.get(self.domain_obj._id)
        self.setup_subscription(self.domain_obj.name, SoftwarePlanEdition.ADVANCED)

        self.sms_backend = TestSMSBackend(named="MOBILE_BACKEND_TEST", is_global=True)
        self.sms_backend.save()

        self.sms_backend_mapping = BackendMapping(is_global=True,prefix="*",backend_id=self.sms_backend._id)
        self.sms_backend_mapping.save()

    def tearDown(self):
        self.sms_backend_mapping.delete()
        self.sms_backend.delete()
        self.teardown_subscription()
        self.domain_obj.delete()


class ReminderTestCase(BaseReminderTestCase):
    """
    This is the original use case and tests a fixed reminder schedule.
    """
    def setUp(self):
        super(ReminderTestCase, self).setUp()
        self.domain = "test"
        self.case_type = "my_case_type"
        self.message = "Hey you're getting this message."
        self.handler = CaseReminderHandler(
            domain=self.domain,
            case_type=self.case_type,
            method=METHOD_SMS,
            start_property='start_sending',
            start_value="ok",
            start_date=None,
            start_offset=1,
            start_match_type=MATCH_EXACT,
            until='stop_sending',
            default_lang='en',
            max_iteration_count=REPEAT_SCHEDULE_INDEFINITELY,
            schedule_length=3,
            event_interpretation=EVENT_AS_OFFSET,
            events = [
                CaseReminderEvent(
                    day_num = 0
                   ,fire_time = time(0,0,0)
                   ,message={"en":self.message}
                   ,callback_timeout_intervals=[]
                )
            ]
        )
        self.handler.save()
        self.user_id = "USER-ID-109347"
        self.user = CommCareUser.create(self.domain, 'chw.bob', '****', uuid=self.user_id, phone_number="99912345")
        self.case = CommCareCase(
            domain=self.domain,
            type=self.case_type,
            user_id=self.user_id,
        )
        self.case.save()

    def tearDown(self):
        self.user.delete()
        super(ReminderTestCase, self).tearDown()

    def test_ok(self):
        self.assertEqual(self.handler.events[0].message['en'], self.message)
        self.assertEqual(self.handler.get_reminder(self.case), None)

        # create reminder
        CaseReminderHandler.now = datetime(year=2011, month=7, day=7, hour=19, minute=8)
        self.case.set_case_property('start_sending', 'ok')
        self.case.save()
        CaseReminderHandler.fire_reminders()
        reminder = self.handler.get_reminder(self.case)
        self.assertNotEqual(reminder, None)
        self.assertEqual(
            reminder.next_fire,
            CaseReminderHandler.now + timedelta(days=self.handler.start_offset)
        )
        self.assertEqual(reminder.last_fired, None)

        # fire a day after created
        CaseReminderHandler.now = datetime(year=2011, month=7, day=8, hour=19, minute=8)
        self.case.set_case_property('irrelevant_1', 'ok')
        self.case.save()
        CaseReminderHandler.fire_reminders()
        reminder = self.handler.get_reminder(self.case)
        self.assertNotEqual(reminder, None)
        self.assertEqual(
            reminder.next_fire,
            CaseReminderHandler.now + timedelta(days=self.handler.schedule_length)
        )
        self.assertEqual(reminder.last_fired, CaseReminderHandler.now)

        # Shouldn't fire until three days after created
        last_fired = CaseReminderHandler.now
        CaseReminderHandler.now = datetime(year=2011, month=7, day=9, hour=19, minute=8)
        CaseReminderHandler.fire_reminders()
        reminder = self.handler.get_reminder(self.case)
        self.assertNotEqual(reminder, None)
        self.assertEqual(reminder.last_fired, last_fired)
        self.assertEqual(
            reminder.next_fire,
            last_fired + timedelta(days=self.handler.schedule_length)
        )

        # fire three days after last fired
        CaseReminderHandler.now = datetime(year=2011, month=7, day=11, hour=19, minute=8)
        self.case.set_case_property('irrelevant_2', 'ok')
        self.case.save()
        CaseReminderHandler.fire_reminders()
        reminder = self.handler.get_reminder(self.case)
        self.assertNotEqual(reminder, None)
        self.assertEqual(
            reminder.next_fire,
            CaseReminderHandler.now + timedelta(days=self.handler.schedule_length)
        )
        self.assertEqual(reminder.last_fired, CaseReminderHandler.now)

        # set stop_sending to 'ok' should make it stop sending and make the reminder inactive
        last_fired = CaseReminderHandler.now
        CaseReminderHandler.now = datetime(year=2011, month=7, day=14, hour=19, minute=8)
        self.case.set_case_property('stop_sending', 'ok')
        self.case.save()
        CaseReminderHandler.fire_reminders()
        reminder = self.handler.get_reminder(self.case)
        self.assertNotEqual(reminder, None)
        self.assertEqual(reminder.last_fired, last_fired)
        self.assertEqual(reminder.active, False)


class ReminderIrregularScheduleTestCase(BaseReminderTestCase):
    """
    This use case represents an irregular reminder schedule which is repeated twice:

    Week1: Day1: 10:00 Message 1
    Week1: Day4: 11:00 Message 2
    Week1: Day4: 11:30 Message 3

    Week2: Day1: 10:00 Message 1
    Week2: Day4: 11:00 Message 2
    Week2: Day4: 11:30 Message 3
    """
    def setUp(self):
        super(ReminderIrregularScheduleTestCase, self).setUp()
        self.domain = "test"
        self.case_type = "my_case_type"
        self.message_1 = "Message 1"
        self.message_2 = "Message 2"
        self.message_3 = "Message 3"
        self.handler = CaseReminderHandler(
            domain=self.domain,
            case_type=self.case_type,
            method=METHOD_SMS,
            start_property='start_sending',
            start_value=None,
            start_date=None,
            start_offset=1,
            start_match_type=MATCH_ANY_VALUE,
            until='stop_sending',
            default_lang='en',
            max_iteration_count=2,
            schedule_length=7,
            event_interpretation=EVENT_AS_SCHEDULE,
            events = [
                CaseReminderEvent(
                    day_num = 0
                   ,fire_time = time(10,00,00)
                   ,message={"en":self.message_1}
                   ,callback_timeout_intervals=[]
                )
               ,CaseReminderEvent(
                    day_num = 3
                   ,fire_time = time(11,00,00)
                   ,message={"en":self.message_2}
                   ,callback_timeout_intervals=[]
                )
               ,CaseReminderEvent(
                    day_num = 3
                   ,fire_time = time(11,30,00)
                   ,message={"en":self.message_3}
                   ,callback_timeout_intervals=[]
                )
            ]
        )
        self.handler.save()
        self.user_id = "USER-ID-109348"
        self.user = CommCareUser.create(self.domain, 'chw.bob2', '****', uuid=self.user_id, phone_number="99912345")
        self.case = CommCareCase(
            domain=self.domain,
            type=self.case_type,
            user_id=self.user_id,
        )
        self.case.save()

    def tearDown(self):
        self.user.delete()
        super(ReminderIrregularScheduleTestCase, self).tearDown()


    def test_ok(self):
        self.assertEqual(self.handler.get_reminder(self.case), None)

        # Spawn CaseReminder
        CaseReminderHandler.now = datetime(year=2012, month=1, day=1, hour=4, minute=0)
        self.case.set_case_property('start_sending', 'ok')
        self.case.save()
        reminder = self.handler.get_reminder(self.case)
        self.assertNotEqual(reminder, None)
        self.assertEqual(reminder.next_fire, datetime(year=2012, month=1, day=2, hour=10, minute=0))
        self.assertEqual(reminder.start_date, date(year=2012, month=1, day=1))
        self.assertEqual(reminder.schedule_iteration_num, 1)
        self.assertEqual(reminder.current_event_sequence_num, 0)
        self.assertEqual(reminder.last_fired, None)
        
        # Not yet the first fire time, nothing should happen
        CaseReminderHandler.now = datetime(year=2012, month=1, day=2, hour=9, minute=45)
        CaseReminderHandler.fire_reminders()
        reminder = self.handler.get_reminder(self.case)
        self.assertNotEqual(reminder, None)
        self.assertEqual(reminder.next_fire, datetime(year=2012, month=1, day=2, hour=10, minute=0))
        self.assertEqual(reminder.schedule_iteration_num, 1)
        self.assertEqual(reminder.current_event_sequence_num, 0)
        self.assertEqual(reminder.last_fired, None)
        
        # Week1, Day1, 10:00 reminder
        CaseReminderHandler.now = datetime(year=2012, month=1, day=2, hour=10, minute=7)
        CaseReminderHandler.fire_reminders()
        reminder = self.handler.get_reminder(self.case)
        self.assertNotEqual(reminder, None)
        self.assertEqual(reminder.next_fire, datetime(year=2012, month=1, day=5, hour=11, minute=0))
        self.assertEqual(reminder.schedule_iteration_num, 1)
        self.assertEqual(reminder.current_event_sequence_num, 1)
        self.assertEqual(reminder.last_fired, CaseReminderHandler.now)
        
        # Week1, Day4, 11:00 reminder
        CaseReminderHandler.now = datetime(year=2012, month=1, day=5, hour=11, minute=3)
        CaseReminderHandler.fire_reminders()
        reminder = self.handler.get_reminder(self.case)
        self.assertNotEqual(reminder, None)
        self.assertEqual(reminder.next_fire, datetime(year=2012, month=1, day=5, hour=11, minute=30))
        self.assertEqual(reminder.schedule_iteration_num, 1)
        self.assertEqual(reminder.current_event_sequence_num, 2)
        self.assertEqual(reminder.last_fired, CaseReminderHandler.now)
        
        # Week1, Day4, 11:30 reminder
        CaseReminderHandler.now = datetime(year=2012, month=1, day=5, hour=11, minute=30)
        CaseReminderHandler.fire_reminders()
        reminder = self.handler.get_reminder(self.case)
        self.assertNotEqual(reminder, None)
        self.assertEqual(reminder.next_fire, datetime(year=2012, month=1, day=9, hour=10, minute=0))
        self.assertEqual(reminder.schedule_iteration_num, 2)
        self.assertEqual(reminder.current_event_sequence_num, 0)
        self.assertEqual(reminder.last_fired, CaseReminderHandler.now)
        
        # Week2, Day1, 10:00 reminder
        CaseReminderHandler.now = datetime(year=2012, month=1, day=9, hour=10, minute=0)
        CaseReminderHandler.fire_reminders()
        reminder = self.handler.get_reminder(self.case)
        self.assertNotEqual(reminder, None)
        self.assertEqual(reminder.next_fire, datetime(year=2012, month=1, day=12, hour=11, minute=0))
        self.assertEqual(reminder.schedule_iteration_num, 2)
        self.assertEqual(reminder.current_event_sequence_num, 1)
        self.assertEqual(reminder.last_fired, CaseReminderHandler.now)
        
        # Week2, Day4, 11:00 reminder
        CaseReminderHandler.now = datetime(year=2012, month=1, day=12, hour=11, minute=0)
        CaseReminderHandler.fire_reminders()
        reminder = self.handler.get_reminder(self.case)
        self.assertNotEqual(reminder, None)
        self.assertEqual(reminder.next_fire, datetime(year=2012, month=1, day=12, hour=11, minute=30))
        self.assertEqual(reminder.schedule_iteration_num, 2)
        self.assertEqual(reminder.current_event_sequence_num, 2)
        self.assertEqual(reminder.last_fired, CaseReminderHandler.now)
        
        # Week2, Day4, 11:30 reminder
        CaseReminderHandler.now = datetime(year=2012, month=1, day=12, hour=11, minute=31)
        CaseReminderHandler.fire_reminders()
        reminder = self.handler.get_reminder(self.case)
        self.assertNotEqual(reminder, None)
        self.assertEqual(reminder.schedule_iteration_num, 3)
        self.assertEqual(reminder.current_event_sequence_num, 0)
        self.assertEqual(reminder.last_fired, CaseReminderHandler.now)
        self.assertEqual(reminder.active, False)


class ReminderCallbackTestCase(BaseReminderTestCase):
    """
    This use case represents a reminder schedule with an expected callback:

    Day1: 10:00 Callback Message 1 [simple reminder]
    Day1: 11:00 Callback Message 2 [expects callback]
    Day1: 11:15 Callback Message 2 [15-minute timeout if callback is not received]
    Day1: 11:45 Callback Message 2 [30-minute timeout if callback is not received]

    Day2: (same as Day1)

    Day3: (same as Day1)

    This case also tests handling of time zones using the timezone of Africa/Nairobi (UTC+3).
    """
    def setUp(self):
        super(ReminderCallbackTestCase, self).setUp()
        self.domain = "test"
        self.case_type = "my_case_type"
        self.message_1 = "Callback Message 1"
        self.message_2 = "Callback Message 2"
        self.handler = CaseReminderHandler(
            domain=self.domain,
            case_type=self.case_type,
            method=METHOD_SMS_CALLBACK,
            start_property='start_sending',
            start_value=None,
            start_date=None,
            start_offset=0,
            start_match_type=MATCH_ANY_VALUE,
            until='stop_sending',
            default_lang='en',
            max_iteration_count=3,
            schedule_length=1,
            event_interpretation=EVENT_AS_SCHEDULE,
            events = [
                CaseReminderEvent(
                    day_num = 0
                   ,fire_time = time(10,00,00)
                   ,message={"en":self.message_1}
                   ,callback_timeout_intervals=[]
                )
               ,CaseReminderEvent(
                    day_num = 0
                   ,fire_time = time(11,00,00)
                   ,message={"en":self.message_2}
                   ,callback_timeout_intervals=[15,30]
                )
            ]
        )
        self.handler.save()
        self.user_id = "USER-ID-109349"
        self.user = CommCareUser.create(self.domain, 'chw.bob3', '****', uuid=self.user_id, phone_number="99912345")
        self.user.user_data["time_zone"]="Africa/Nairobi"
        self.user.save()
        self.case = CommCareCase(
            domain=self.domain,
            type=self.case_type,
            user_id=self.user_id
        )
        self.case.save()
        self.user.save_verified_number("test", "14445551234", True, None)

    def tearDown(self):
        self.user.delete()
        super(ReminderCallbackTestCase, self).tearDown()

    def test_ok(self):
        self.assertEqual(self.handler.get_reminder(self.case), None)

        # Spawn CaseReminder
        CaseReminderHandler.now = datetime(year=2011, month=12, day=31, hour=23, minute=0)
        self.case.set_case_property('start_sending', 'ok')
        self.case.save()
        reminder = self.handler.get_reminder(self.case)
        self.assertNotEqual(reminder, None)
        self.assertEqual(reminder.next_fire, datetime(year=2012, month=1, day=1, hour=7, minute=0))
        self.assertEqual(reminder.start_date, date(year=2012, month=1, day=1))
        self.assertEqual(reminder.schedule_iteration_num, 1)
        self.assertEqual(reminder.current_event_sequence_num, 0)
        self.assertEqual(reminder.last_fired, None)
        
        ######################
        # Day1, 10:00 reminder
        CaseReminderHandler.now = datetime(year=2012, month=1, day=1, hour=7, minute=0)
        CaseReminderHandler.fire_reminders()
        reminder = self.handler.get_reminder(self.case)
        self.assertNotEqual(reminder, None)
        self.assertEqual(reminder.next_fire, datetime(year=2012, month=1, day=1, hour=8, minute=0))
        self.assertEqual(reminder.schedule_iteration_num, 1)
        self.assertEqual(reminder.current_event_sequence_num, 1)
        self.assertEqual(reminder.last_fired, CaseReminderHandler.now)
        
        # Day1, 11:00 reminder
        CaseReminderHandler.now = datetime(year=2012, month=1, day=1, hour=8, minute=1)
        CaseReminderHandler.fire_reminders()
        reminder = self.handler.get_reminder(self.case)
        self.assertNotEqual(reminder, None)
        self.assertEqual(reminder.next_fire, datetime(year=2012, month=1, day=1, hour=8, minute=15))
        self.assertEqual(reminder.schedule_iteration_num, 1)
        self.assertEqual(reminder.current_event_sequence_num, 1)
        self.assertEqual(reminder.last_fired, CaseReminderHandler.now)
        
        event = ExpectedCallbackEventLog.view("sms/expected_callback_event",
                                              key=["test", json_format_datetime(datetime(year=2012, month=1, day=1, hour=8, minute=1)), self.user_id],
                                              include_docs=True).one()
        self.assertNotEqual(event, None)
        self.assertEqual(event.status, CALLBACK_PENDING)
        
        # Create a callback
        c = CallLog(
            couch_recipient_doc_type    = "CommCareUser",
            couch_recipient             = self.user_id,
            phone_number                = "14445551234",
            direction                   = "I",
            date                        = datetime(year=2012, month=1, day=1, hour=8, minute=5)
        )
        c.save()

        # Day1, 11:15 timeout (should move on to next event)
        CaseReminderHandler.now = datetime(year=2012, month=1, day=1, hour=8, minute=15)
        CaseReminderHandler.fire_reminders()
        reminder = self.handler.get_reminder(self.case)
        self.assertNotEqual(reminder, None)
        self.assertEqual(reminder.next_fire, datetime(year=2012, month=1, day=1, hour=8, minute=45))
        self.assertEqual(reminder.schedule_iteration_num, 1)
        self.assertEqual(reminder.current_event_sequence_num, 1)
        self.assertEqual(reminder.last_fired, CaseReminderHandler.now)

        # Day1, 11:45 timeout (should move on to next event)
        CaseReminderHandler.now = datetime(year=2012, month=1, day=1, hour=8, minute=45)
        CaseReminderHandler.fire_reminders()
        reminder = self.handler.get_reminder(self.case)
        self.assertNotEqual(reminder, None)
        self.assertEqual(reminder.next_fire, datetime(year=2012, month=1, day=2, hour=7, minute=0))
        self.assertEqual(reminder.schedule_iteration_num, 2)
        self.assertEqual(reminder.current_event_sequence_num, 0)
        self.assertEqual(reminder.last_fired, CaseReminderHandler.now)

        event = ExpectedCallbackEventLog.view("sms/expected_callback_event",
                                              key=["test", json_format_datetime(datetime(year=2012, month=1, day=1, hour=8, minute=1)), self.user_id],
                                              include_docs=True).one()
        self.assertNotEqual(event, None)
        self.assertEqual(event.status, CALLBACK_RECEIVED)

        ######################
        # Day2, 10:00 reminder
        CaseReminderHandler.now = datetime(year=2012, month=1, day=2, hour=7, minute=0)
        CaseReminderHandler.fire_reminders()
        reminder = self.handler.get_reminder(self.case)
        self.assertNotEqual(reminder, None)
        self.assertEqual(reminder.next_fire, datetime(year=2012, month=1, day=2, hour=8, minute=0))
        self.assertEqual(reminder.schedule_iteration_num, 2)
        self.assertEqual(reminder.current_event_sequence_num, 1)
        self.assertEqual(reminder.last_fired, CaseReminderHandler.now)
        
        # Day2, 11:00 reminder
        CaseReminderHandler.now = datetime(year=2012, month=1, day=2, hour=8, minute=1)
        CaseReminderHandler.fire_reminders()
        reminder = self.handler.get_reminder(self.case)
        self.assertNotEqual(reminder, None)
        self.assertEqual(reminder.next_fire, datetime(year=2012, month=1, day=2, hour=8, minute=15))
        self.assertEqual(reminder.schedule_iteration_num, 2)
        self.assertEqual(reminder.current_event_sequence_num, 1)
        self.assertEqual(reminder.last_fired, CaseReminderHandler.now)
        
        event = ExpectedCallbackEventLog.view("sms/expected_callback_event",
                                              key=["test", json_format_datetime(datetime(year=2012, month=1, day=2, hour=8, minute=1)), self.user_id],
                                              include_docs=True).one()
        self.assertNotEqual(event, None)
        self.assertEqual(event.status, CALLBACK_PENDING)
        
        # Day2, 11:15 timeout (should move on to next timeout)
        CaseReminderHandler.now = datetime(year=2012, month=1, day=2, hour=8, minute=15)
        CaseReminderHandler.fire_reminders()
        reminder = self.handler.get_reminder(self.case)
        self.assertNotEqual(reminder, None)
        self.assertEqual(reminder.next_fire, datetime(year=2012, month=1, day=2, hour=8, minute=45))
        self.assertEqual(reminder.schedule_iteration_num, 2)
        self.assertEqual(reminder.current_event_sequence_num, 1)
        self.assertEqual(reminder.last_fired, CaseReminderHandler.now)
        
        event = ExpectedCallbackEventLog.view("sms/expected_callback_event",
                                              key=["test", json_format_datetime(datetime(year=2012, month=1, day=2, hour=8, minute=1)), self.user_id],
                                              include_docs=True).one()
        self.assertNotEqual(event, None)
        self.assertEqual(event.status, CALLBACK_PENDING)
        
        # Day2, 11:45 timeout (should move on to next day)
        CaseReminderHandler.now = datetime(year=2012, month=1, day=2, hour=8, minute=45)
        CaseReminderHandler.fire_reminders()
        reminder = self.handler.get_reminder(self.case)
        self.assertNotEqual(reminder, None)
        self.assertEqual(reminder.next_fire, datetime(year=2012, month=1, day=3, hour=7, minute=0))
        self.assertEqual(reminder.schedule_iteration_num, 3)
        self.assertEqual(reminder.current_event_sequence_num, 0)
        self.assertEqual(reminder.last_fired, CaseReminderHandler.now)
        
        event = ExpectedCallbackEventLog.view("sms/expected_callback_event",
                                              key=["test", json_format_datetime(datetime(year=2012, month=1, day=2, hour=8, minute=1)), self.user_id],
                                              include_docs=True).one()
        self.assertNotEqual(event, None)
        self.assertEqual(event.status, CALLBACK_MISSED)
        
        ######################
        # Day3, 10:00 reminder
        CaseReminderHandler.now = datetime(year=2012, month=1, day=3, hour=7, minute=0)
        CaseReminderHandler.fire_reminders()
        reminder = self.handler.get_reminder(self.case)
        self.assertNotEqual(reminder, None)
        self.assertEqual(reminder.next_fire, datetime(year=2012, month=1, day=3, hour=8, minute=0))
        self.assertEqual(reminder.schedule_iteration_num, 3)
        self.assertEqual(reminder.current_event_sequence_num, 1)
        self.assertEqual(reminder.last_fired, CaseReminderHandler.now)
        
        # Day3, 11:00 reminder
        CaseReminderHandler.now = datetime(year=2012, month=1, day=3, hour=8, minute=1)
        CaseReminderHandler.fire_reminders()
        reminder = self.handler.get_reminder(self.case)
        self.assertNotEqual(reminder, None)
        self.assertEqual(reminder.next_fire, datetime(year=2012, month=1, day=3, hour=8, minute=15))
        self.assertEqual(reminder.schedule_iteration_num, 3)
        self.assertEqual(reminder.current_event_sequence_num, 1)
        self.assertEqual(reminder.last_fired, CaseReminderHandler.now)
        
        event = ExpectedCallbackEventLog.view("sms/expected_callback_event",
                                              key=["test", json_format_datetime(datetime(year=2012, month=1, day=3, hour=8, minute=1)), self.user_id],
                                              include_docs=True).one()
        self.assertNotEqual(event, None)
        self.assertEqual(event.status, CALLBACK_PENDING)
        
        # Day3, 11:15 timeout (should move on to next timeout)
        CaseReminderHandler.now = datetime(year=2012, month=1, day=3, hour=8, minute=15)
        CaseReminderHandler.fire_reminders()
        reminder = self.handler.get_reminder(self.case)
        self.assertNotEqual(reminder, None)
        self.assertEqual(reminder.next_fire, datetime(year=2012, month=1, day=3, hour=8, minute=45))
        self.assertEqual(reminder.schedule_iteration_num, 3)
        self.assertEqual(reminder.current_event_sequence_num, 1)
        self.assertEqual(reminder.last_fired, CaseReminderHandler.now)
        
        event = ExpectedCallbackEventLog.view("sms/expected_callback_event",
                                              key=["test", json_format_datetime(datetime(year=2012, month=1, day=3, hour=8, minute=1)), self.user_id],
                                              include_docs=True).one()
        self.assertNotEqual(event, None)
        self.assertEqual(event.status, CALLBACK_PENDING)
        
        # Create a callback (with phone_number missing country code)
        c = CallLog(
            couch_recipient_doc_type    = "CommCareUser",
            couch_recipient             = self.user_id,
            phone_number                = "4445551234",
            direction                   = "I",
            date                        = datetime(year=2012, month=1, day=3, hour=8, minute=22)
        )
        c.save()
        
        # Day3, 11:45 timeout (should deactivate the reminder)
        CaseReminderHandler.now = datetime(year=2012, month=1, day=3, hour=8, minute=45)
        CaseReminderHandler.fire_reminders()
        reminder = self.handler.get_reminder(self.case)
        self.assertNotEqual(reminder, None)
        self.assertEqual(reminder.schedule_iteration_num, 4)
        self.assertEqual(reminder.current_event_sequence_num, 0)
        self.assertEqual(reminder.last_fired, CaseReminderHandler.now)
        self.assertEqual(reminder.active, False)
        
        event = ExpectedCallbackEventLog.view("sms/expected_callback_event",
                                              key=["test", json_format_datetime(datetime(year=2012, month=1, day=3, hour=8, minute=1)), self.user_id],
                                              include_docs=True).one()
        self.assertNotEqual(event, None)
        self.assertEqual(event.status, CALLBACK_RECEIVED)


class CaseTypeReminderTestCase(BaseReminderTestCase):
    def setUp(self):
        super(CaseTypeReminderTestCase, self).setUp()
        self.domain = "test"
        self.user_id = "USER-ID-109350"
        self.user = CommCareUser.create(self.domain, 'chw.bob4', '****', uuid=self.user_id, phone_number="99912345")
        
        self.handler1 = CaseReminderHandler(
            domain=self.domain,
            case_type="case_type_a",
            method=METHOD_SMS,
            start_property='start_sending1',
            start_value=None,
            start_date=None,
            start_offset=1,
            start_match_type=MATCH_ANY_VALUE,
            until='stop_sending1',
            default_lang='en',
            max_iteration_count=REPEAT_SCHEDULE_INDEFINITELY,
            schedule_length=3,
            event_interpretation=EVENT_AS_OFFSET,
            events = [
                CaseReminderEvent(
                    day_num = 0
                   ,fire_time = time(0,0,0)
                   ,message={"en":"Message1"}
                   ,callback_timeout_intervals=[]
                )
            ]
        )
        self.handler1.save()
        
        self.handler2 = CaseReminderHandler(
            domain=self.domain,
            case_type="case_type_a",
            method=METHOD_SMS,
            start_property='start_sending2',
            start_value=None,
            start_date=None,
            start_offset=2,
            start_match_type=MATCH_ANY_VALUE,
            until='stop_sending2',
            default_lang='en',
            max_iteration_count=REPEAT_SCHEDULE_INDEFINITELY,
            schedule_length=3,
            event_interpretation=EVENT_AS_OFFSET,
            events = [
                CaseReminderEvent(
                    day_num = 0
                   ,fire_time = time(0,0,0)
                   ,message={"en":"Message2"}
                   ,callback_timeout_intervals=[]
                )
            ]
        )
        self.handler2.save()
        
        self.handler3 = CaseReminderHandler(
            domain=self.domain,
            case_type="case_type_a",
            method=METHOD_SMS,
            start_property='start_sending3',
            start_value=None,
            start_date=None,
            start_offset=3,
            start_match_type=MATCH_ANY_VALUE,
            until='stop_sending3',
            default_lang='en',
            max_iteration_count=REPEAT_SCHEDULE_INDEFINITELY,
            schedule_length=3,
            event_interpretation=EVENT_AS_OFFSET,
            events = [
                CaseReminderEvent(
                    day_num = 0
                   ,fire_time = time(0,0,0)
                   ,message={"en":"Message3"}
                   ,callback_timeout_intervals=[]
                )
            ]
        )
        self.handler3.save()
        
        self.case1 = CommCareCase(
            domain=self.domain,
            type="case_type_a",
            user_id=self.user_id
        )
        self.case1.save()
        
        self.case2 = CommCareCase(
            domain=self.domain,
            type="case_type_b",
            user_id=self.user_id
        )
        self.case2.save()

    def tearDown(self):
        self.user.delete()
        super(CaseTypeReminderTestCase, self).tearDown()

    def test_ok(self):
        # Initial condition
        CaseReminderHandler.now = datetime(year=2012, month=2, day=16, hour=11, minute=0)
        
        self.case1.set_case_property("start_sending1", "ok")
        self.case1.set_case_property("start_sending2", "ok")
        self.case2.set_case_property("start_sending1", "ok")
        self.case2.set_case_property("start_sending3", "ok")
        self.case1.save()
        self.case2.save()
        
        self.assertNotEqual(self.handler1.get_reminder(self.case1), None)
        self.assertEqual(self.handler1.get_reminder(self.case2), None)
        self.assertNotEqual(self.handler2.get_reminder(self.case1), None)
        self.assertEqual(self.handler2.get_reminder(self.case2), None)
        self.assertEqual(self.handler3.get_reminder(self.case1), None)
        self.assertEqual(self.handler3.get_reminder(self.case2), None)
        
        self.assertEqual(
            self.handler1.get_reminder(self.case1).next_fire
           ,CaseReminderHandler.now + timedelta(days=self.handler1.start_offset)
        )
        self.assertEqual(
            self.handler2.get_reminder(self.case1).next_fire
           ,CaseReminderHandler.now + timedelta(days=self.handler2.start_offset)
        )
        
        # Test deactivation and spawn on change of CaseReminderHandler.case_type
        CaseReminderHandler.now = datetime(year=2012, month=2, day=16, hour=11, minute=15)
        
        self.handler1.case_type = "case_type_b"
        self.handler1.save()
        self.handler2.case_type = "case_type_b"
        self.handler2.save()
        self.handler3.case_type = "case_type_b"
        self.handler3.save()
        
        self.assertEqual(self.handler1.get_reminder(self.case1), None)
        self.assertNotEqual(self.handler1.get_reminder(self.case2), None)
        self.assertEqual(self.handler2.get_reminder(self.case1), None)
        self.assertEqual(self.handler2.get_reminder(self.case2), None)
        self.assertEqual(self.handler3.get_reminder(self.case1), None)
        self.assertNotEqual(self.handler3.get_reminder(self.case2), None)
        
        self.assertEqual(
            self.handler1.get_reminder(self.case2).next_fire
           ,CaseReminderHandler.now + timedelta(days=self.handler1.start_offset)
        )
        self.assertEqual(
            self.handler3.get_reminder(self.case2).next_fire
           ,CaseReminderHandler.now + timedelta(days=self.handler3.start_offset)
        )
        
        # Test spawn on change of Case.type
        prev_now = CaseReminderHandler.now
        CaseReminderHandler.now = datetime(year=2012, month=2, day=16, hour=11, minute=30)
        
        self.case1.type = "case_type_b"
        self.case1.save()
        
        self.assertNotEqual(self.handler1.get_reminder(self.case1), None)
        self.assertNotEqual(self.handler1.get_reminder(self.case2), None)
        self.assertNotEqual(self.handler2.get_reminder(self.case1), None)
        self.assertEqual(self.handler2.get_reminder(self.case2), None)
        self.assertEqual(self.handler3.get_reminder(self.case1), None)
        self.assertNotEqual(self.handler3.get_reminder(self.case2), None)
        
        self.assertEqual(
            self.handler1.get_reminder(self.case1).next_fire
           ,CaseReminderHandler.now + timedelta(days=self.handler1.start_offset)
        )
        self.assertEqual(
            self.handler2.get_reminder(self.case1).next_fire
           ,CaseReminderHandler.now + timedelta(days=self.handler2.start_offset)
        )
        
        self.assertEqual(
            self.handler1.get_reminder(self.case2).next_fire
           ,prev_now + timedelta(days=self.handler1.start_offset)
        )
        self.assertEqual(
            self.handler3.get_reminder(self.case2).next_fire
           ,prev_now + timedelta(days=self.handler3.start_offset)
        )
        
        # Test deactivation on change of Case.type
        prev_now = CaseReminderHandler.now
        CaseReminderHandler.now = datetime(year=2012, month=2, day=16, hour=11, minute=45)
        
        self.case2.type = "case_type_a"
        self.case2.save()
        
        self.assertNotEqual(self.handler1.get_reminder(self.case1), None)
        self.assertEqual(self.handler1.get_reminder(self.case2), None)
        self.assertNotEqual(self.handler2.get_reminder(self.case1), None)
        self.assertEqual(self.handler2.get_reminder(self.case2), None)
        self.assertEqual(self.handler3.get_reminder(self.case1), None)
        self.assertEqual(self.handler3.get_reminder(self.case2), None)
        
        self.assertEqual(
            self.handler1.get_reminder(self.case1).next_fire
           ,prev_now + timedelta(days=self.handler1.start_offset)
        )
        self.assertEqual(
            self.handler2.get_reminder(self.case1).next_fire
           ,prev_now + timedelta(days=self.handler2.start_offset)
        )

class StartConditionReminderTestCase(BaseReminderTestCase):
    def setUp(self):
        super(StartConditionReminderTestCase, self).setUp()
        self.domain = "test"
        self.user_id = "USER-ID-109351"
        self.user = CommCareUser.create(self.domain, 'chw.bob5', '****', uuid=self.user_id, phone_number="99912345")
        
        self.handler1 = CaseReminderHandler(
            domain=self.domain,
            case_type="case_type_a",
            method=METHOD_SMS,
            start_property='start_sending1',
            start_value="^(ok|OK|\d\d\d\d-\d\d-\d\d)",
            start_date='start_sending1',
            start_offset=1,
            start_match_type=MATCH_REGEX,
            until='stop_sending1',
            default_lang='en',
            max_iteration_count=REPEAT_SCHEDULE_INDEFINITELY,
            schedule_length=3,
            event_interpretation=EVENT_AS_OFFSET,
            events = [
                CaseReminderEvent(
                    day_num = 0
                   ,fire_time = time(0,0,0)
                   ,message={"en":"Message1"}
                   ,callback_timeout_intervals=[]
                )
            ]
        )
        self.handler1.save()
        
        self.case1 = CommCareCase(
            domain=self.domain,
            type="case_type_a",
            user_id=self.user_id
        )
        self.case1.save()

    def tearDown(self):
        self.user.delete()
        super(StartConditionReminderTestCase, self).tearDown()


    def test_ok(self):
        #
        # Test changing a start condition of "ok"
        #
        # Spawn the reminder with an "ok" start condition value
        CaseReminderHandler.now = datetime(year=2012, month=2, day=17, hour=12, minute=0)
        self.assertEqual(self.handler1.get_reminder(self.case1), None)
        
        self.case1.set_case_property("start_sending1", "ok")
        self.case1.save()
        
        reminder = self.handler1.get_reminder(self.case1)
        self.assertNotEqual(reminder, None)
        
        self.assertEqual(
            reminder.next_fire
           ,CaseReminderHandler.now + timedelta(days=self.handler1.start_offset)
        )
        
        # Test that saving the case without changing the start condition has no effect
        old_reminder_id = reminder._id
        self.case1.set_case_property("case_property1", "abc")
        self.case1.save()
        reminder = self.handler1.get_reminder(self.case1)
        self.assertNotEqual(reminder, None)
        self.assertEqual(reminder._id, old_reminder_id)
        
        # Test retiring the reminder
        old_reminder_id = reminder._id
        self.case1.set_case_property("start_sending1", None)
        self.case1.save()
        
        self.assertEqual(self.handler1.get_reminder(self.case1), None)
        self.assertEqual(CaseReminder.get(old_reminder_id).doc_type, "CaseReminder-Deleted")
        
        #
        # Test changing a start condition which is a datetime value
        #
        # Spawn the reminder with datetime start condition value
        start = datetime(2012,2,20,9,0,0)
        self.case1.set_case_property("start_sending1", start)
        self.case1.save()
        
        reminder = self.handler1.get_reminder(self.case1)
        self.assertNotEqual(reminder, None)
        
        self.assertEqual(
            reminder.next_fire
           ,start + timedelta(days=self.handler1.start_offset)
        )
        
        # Reset the datetime start condition
        old_reminder_id = reminder._id
        start = datetime(2012,2,22,10,15,0)
        self.case1.set_case_property("start_sending1", start)
        self.case1.save()
        
        reminder = self.handler1.get_reminder(self.case1)
        self.assertNotEqual(reminder, None)
        
        self.assertEqual(
            reminder.next_fire
           ,start + timedelta(days=self.handler1.start_offset)
        )
        self.assertEqual(CaseReminder.get(old_reminder_id).doc_type, "CaseReminder-Deleted")
        
        # Test that saving the case without changing the start condition has no effect
        old_reminder_id = reminder._id
        self.case1.set_case_property("case_property1", "xyz")
        self.case1.save()
        reminder = self.handler1.get_reminder(self.case1)
        self.assertNotEqual(reminder, None)
        self.assertEqual(reminder._id, old_reminder_id)
        
        # Retire the reminder
        old_reminder_id = reminder._id
        self.case1.set_case_property("start_sending1", None)
        self.case1.save()
        
        reminder = self.handler1.get_reminder(self.case1)
        self.assertEqual(reminder, None)
        self.assertEqual(CaseReminder.get(old_reminder_id).doc_type, "CaseReminder-Deleted")
        
        #
        # Test changing a start condition which is a date value
        #
        # Spawn the reminder with date start condition value
        start = date(2012,2,20)
        self.case1.set_case_property("start_sending1", start)
        self.case1.save()
        
        reminder = self.handler1.get_reminder(self.case1)
        self.assertNotEqual(reminder, None)
        
        self.assertEqual(
            reminder.next_fire
           ,datetime(start.year, start.month, start.day) + timedelta(days=self.handler1.start_offset)
        )
        
        # Reset the date start condition
        old_reminder_id = reminder._id
        start = date(2012,2,22)
        self.case1.set_case_property("start_sending1", start)
        self.case1.save()
        
        reminder = self.handler1.get_reminder(self.case1)
        self.assertNotEqual(reminder, None)
        
        self.assertEqual(
            reminder.next_fire
           ,datetime(start.year, start.month, start.day) + timedelta(days=self.handler1.start_offset)
        )
        self.assertEqual(CaseReminder.get(old_reminder_id).doc_type, "CaseReminder-Deleted")
        
        # Test that saving the case without changing the start condition has no effect
        old_reminder_id = reminder._id
        self.case1.set_case_property("case_property1", "abc")
        self.case1.save()
        reminder = self.handler1.get_reminder(self.case1)
        self.assertNotEqual(reminder, None)
        self.assertEqual(reminder._id, old_reminder_id)
        
        # Retire the reminder
        old_reminder_id = reminder._id
        self.case1.set_case_property("start_sending1", None)
        self.case1.save()
        
        reminder = self.handler1.get_reminder(self.case1)
        self.assertEqual(reminder, None)
        self.assertEqual(CaseReminder.get(old_reminder_id).doc_type, "CaseReminder-Deleted")
        
        #
        # Test changing a start condition which is a string representation of a datetime value
        #
        # Spawn the reminder with datetime start condition value
        self.case1.set_case_property("start_sending1", "2012-02-25 11:15")
        self.case1.save()
        
        reminder = self.handler1.get_reminder(self.case1)
        self.assertNotEqual(reminder, None)
        
        self.assertEqual(
            reminder.next_fire
           ,datetime(2012,2,25,11,15) + timedelta(days=self.handler1.start_offset)
        )
        
        # Reset the datetime start condition
        old_reminder_id = reminder._id
        self.case1.set_case_property("start_sending1", "2012-02-26 11:20")
        self.case1.save()
        
        reminder = self.handler1.get_reminder(self.case1)
        self.assertNotEqual(reminder, None)
        
        self.assertEqual(
            reminder.next_fire
           ,datetime(2012,2,26,11,20) + timedelta(days=self.handler1.start_offset)
        )
        self.assertEqual(CaseReminder.get(old_reminder_id).doc_type, "CaseReminder-Deleted")
        
        # Test that saving the case without changing the start condition has no effect
        old_reminder_id = reminder._id
        self.case1.set_case_property("case_property1", "xyz")
        self.case1.save()
        reminder = self.handler1.get_reminder(self.case1)
        self.assertNotEqual(reminder, None)
        self.assertEqual(reminder._id, old_reminder_id)
        
        # Retire the reminder
        old_reminder_id = reminder._id
        self.case1.set_case_property("start_sending1", None)
        self.case1.save()
        
        reminder = self.handler1.get_reminder(self.case1)
        self.assertEqual(reminder, None)
        self.assertEqual(CaseReminder.get(old_reminder_id).doc_type, "CaseReminder-Deleted")

class ReminderLockTestCase(BaseReminderTestCase):
    def setUp(self):
        super(ReminderLockTestCase, self).setUp()
        self.domain = "test"
        self.user_id = "USER-ID-109352"
        self.user = CommCareUser.create(self.domain, 'chw.bob6', '****', uuid=self.user_id, phone_number="99912345")
        
        self.handler1 = CaseReminderHandler(
            domain=self.domain,
            case_type="case_type_a",
            method=METHOD_SMS,
            start_property='start_sending1',
            start_value="^(ok|OK|\d\d\d\d-\d\d-\d\d)",
            start_date='start_sending1',
            start_offset=1,
            start_match_type=MATCH_REGEX,
            until='stop_sending1',
            default_lang='en',
            max_iteration_count=REPEAT_SCHEDULE_INDEFINITELY,
            schedule_length=3,
            event_interpretation=EVENT_AS_OFFSET,
            events = [
                CaseReminderEvent(
                    day_num = 0
                   ,fire_time = time(0,0,0)
                   ,message={"en":"Testing the lock"}
                   ,callback_timeout_intervals=[]
                )
            ]
        )
        self.handler1.save()
        
        self.case1 = CommCareCase(
            domain=self.domain,
            type="case_type_a",
            user_id=self.user_id
        )
        self.case1.save()

    def tearDown(self):
        self.user.delete()
        super(ReminderLockTestCase, self).tearDown()


    def test_ok(self):
        # Spawn the reminder with an "ok" start condition value
        CaseReminderHandler.now = datetime(year=2012, month=2, day=17, hour=12, minute=0)
        self.assertEqual(self.handler1.get_reminder(self.case1), None)
        
        self.case1.set_case_property("start_sending1", "ok")
        self.case1.save()
        
        reminder = self.handler1.get_reminder(self.case1)
        old_reminder = self.handler1.get_reminder(self.case1)
        self.assertNotEqual(reminder, None)
        
        self.assertEqual(
            reminder.next_fire
           ,CaseReminderHandler.now + timedelta(days=self.handler1.start_offset)
        )
        
        # Fire the reminder, testing that the locking process works
        CaseReminderHandler.now = datetime(year=2012, month=2, day=18, hour=12, minute=1)
        self.assertEqual(reminder.lock_date, None)
        self.assertEqual(reminder.acquire_lock(CaseReminderHandler.now), True)
        self.assertEqual(reminder.lock_date, CaseReminderHandler.now)
        self.assertEqual(reminder.acquire_lock(CaseReminderHandler.now), False)
        self.handler1.fire(reminder)
        self.handler1.set_next_fire(reminder, CaseReminderHandler.now)
        reminder.release_lock()
        self.assertEqual(reminder.lock_date, None)
        
        # Ensure old versions of the document cannot acquire the lock
        self.assertNotEqual(reminder._rev, old_reminder._rev)
        self.assertEqual(old_reminder.acquire_lock(CaseReminderHandler.now), False)
        
        # Test the lock timeout
        self.assertEqual(reminder.acquire_lock(CaseReminderHandler.now), True)
        self.assertEqual(reminder.acquire_lock(CaseReminderHandler.now), False)
        self.assertEqual(reminder.acquire_lock(CaseReminderHandler.now + LOCK_EXPIRATION + timedelta(minutes = 1)), True)


class MessageTestCase(BaseReminderTestCase):

    def setUp(self):
        self.domain = "test"

        self.parent_case = CommCareCase(
            domain=self.domain,
            type="parent",
            name="P001",
        )
        self.parent_case.set_case_property("parent_prop1", "abc")
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
        self.child_case.set_case_property("child_prop1", "def")
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


class ReminderDefinitionCalculationsTestCase(TestCase):
    def test_calculate_start_date_without_today_option(self):
        now = datetime.utcnow()

        reminder = CaseReminderHandler(
            domain='reminder-calculation-test',
            use_today_if_start_date_is_blank=False
        )

        case = CommCareCase(
            domain='reminder-calculation-test',
        )

        self.assertEqual(
            reminder.get_case_criteria_reminder_start_date(case, now),
            (now, True, True)
        )

        reminder.start_date = 'start_date_case_property'
        self.assertEqual(
            reminder.get_case_criteria_reminder_start_date(case, now),
            (None, False, False)
        )

        case.set_case_property('start_date_case_property', '')
        self.assertEqual(
            reminder.get_case_criteria_reminder_start_date(case, now),
            (None, False, False)
        )

        case.set_case_property('start_date_case_property', '   ')
        self.assertEqual(
            reminder.get_case_criteria_reminder_start_date(case, now),
            (None, False, False)
        )

        case.set_case_property('start_date_case_property', 'abcdefg')
        self.assertEqual(
            reminder.get_case_criteria_reminder_start_date(case, now),
            (None, False, False)
        )

        case.set_case_property('start_date_case_property', '2016-01-32')
        self.assertEqual(
            reminder.get_case_criteria_reminder_start_date(case, now),
            (None, False, False)
        )

        case.set_case_property('start_date_case_property', '2016-01-10')
        self.assertEqual(
            reminder.get_case_criteria_reminder_start_date(case, now),
            (datetime(2016, 1, 10), True, False)
        )

        case.set_case_property('start_date_case_property', date(2016, 1, 11))
        self.assertEqual(
            reminder.get_case_criteria_reminder_start_date(case, now),
            (datetime(2016, 1, 11), True, False)
        )

        case.set_case_property('start_date_case_property', datetime(2016, 1, 12))
        self.assertEqual(
            reminder.get_case_criteria_reminder_start_date(case, now),
            (datetime(2016, 1, 12), True, False)
        )

    def test_calculate_start_date_with_today_option(self):
        now = datetime.utcnow()

        reminder = CaseReminderHandler(
            domain='reminder-calculation-test',
            use_today_if_start_date_is_blank=True
        )

        case = CommCareCase(
            domain='reminder-calculation-test',
        )

        self.assertEqual(
            reminder.get_case_criteria_reminder_start_date(case, now),
            (now, True, True)
        )

        reminder.start_date = 'start_date_case_property'
        self.assertEqual(
            reminder.get_case_criteria_reminder_start_date(case, now),
            (now, True, True)
        )

        case.set_case_property('start_date_case_property', '')
        self.assertEqual(
            reminder.get_case_criteria_reminder_start_date(case, now),
            (now, True, True)
        )

        case.set_case_property('start_date_case_property', '   ')
        self.assertEqual(
            reminder.get_case_criteria_reminder_start_date(case, now),
            (now, True, True)
        )

        case.set_case_property('start_date_case_property', 'abcdefg')
        self.assertEqual(
            reminder.get_case_criteria_reminder_start_date(case, now),
            (now, True, True)
        )

        case.set_case_property('start_date_case_property', '2016-01-32')
        self.assertEqual(
            reminder.get_case_criteria_reminder_start_date(case, now),
            (now, True, True)
        )

        case.set_case_property('start_date_case_property', '2016-01-10')
        self.assertEqual(
            reminder.get_case_criteria_reminder_start_date(case, now),
            (datetime(2016, 1, 10), True, False)
        )

        case.set_case_property('start_date_case_property', date(2016, 1, 11))
        self.assertEqual(
            reminder.get_case_criteria_reminder_start_date(case, now),
            (datetime(2016, 1, 11), True, False)
        )

        case.set_case_property('start_date_case_property', datetime(2016, 1, 12))
        self.assertEqual(
            reminder.get_case_criteria_reminder_start_date(case, now),
            (datetime(2016, 1, 12), True, False)
        )
