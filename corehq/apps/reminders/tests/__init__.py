from datetime import datetime, timedelta, date, time
from django.test.testcases import TestCase
from casexml.apps.case.models import CommCareCase
from corehq.apps.reminders.models import *
from corehq.apps.users.models import CouchUser, CommCareUser
from corehq.apps.sms.models import CallLog, EventLog, MISSED_EXPECTED_CALLBACK
from corehq.apps.sms.mixin import VerifiedNumber
from dimagi.utils.parsing import json_format_datetime
from dimagi.utils.couch import LOCK_EXPIRATION

class ReminderTestCase(TestCase):
    """
    This is the original use case and tests a fixed reminder schedule.
    """
    @classmethod
    def setUpClass(cls):
        cls.domain = "test"
        cls.case_type = "my_case_type"
        cls.message = "Hey you're getting this message."
        cls.handler = CaseReminderHandler(
            domain=cls.domain,
            case_type=cls.case_type,
            method="test",
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
                   ,message={"en":cls.message}
                   ,callback_timeout_intervals=[]
                )
            ]
        )
        cls.handler.save()
        cls.user_id = "USER-ID-109347"
        cls.user = CommCareUser.create(cls.domain, 'chw.bob', '****', uuid=cls.user_id)
        cls.case = CommCareCase(
            domain=cls.domain,
            type=cls.case_type,
            user_id=cls.user_id,
        )
        cls.case.save()

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

    @classmethod
    def tearDownClass(cls):
        pass

class ReminderIrregularScheduleTestCase(TestCase):
    """
    This use case represents an irregular reminder schedule which is repeated twice:

    Week1: Day1: 10:00 Message 1
    Week1: Day4: 11:00 Message 2
    Week1: Day4: 11:30 Message 3

    Week2: Day1: 10:00 Message 1
    Week2: Day4: 11:00 Message 2
    Week2: Day4: 11:30 Message 3
    """
    @classmethod
    def setUpClass(cls):
        cls.domain = "test"
        cls.case_type = "my_case_type"
        cls.message_1 = "Message 1"
        cls.message_2 = "Message 2"
        cls.message_3 = "Message 3"
        cls.handler = CaseReminderHandler(
            domain=cls.domain,
            case_type=cls.case_type,
            method="test",
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
                   ,message={"en":cls.message_1}
                   ,callback_timeout_intervals=[]
                )
               ,CaseReminderEvent(
                    day_num = 3
                   ,fire_time = time(11,00,00)
                   ,message={"en":cls.message_2}
                   ,callback_timeout_intervals=[]
                )
               ,CaseReminderEvent(
                    day_num = 3
                   ,fire_time = time(11,30,00)
                   ,message={"en":cls.message_3}
                   ,callback_timeout_intervals=[]
                )
            ]
        )
        cls.handler.save()
        cls.user_id = "USER-ID-109348"
        cls.user = CommCareUser.create(cls.domain, 'chw.bob2', '****', uuid=cls.user_id)
        cls.case = CommCareCase(
            domain=cls.domain,
            type=cls.case_type,
            user_id=cls.user_id,
        )
        cls.case.save()

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


    @classmethod
    def tearDownClass(cls):
        pass

class ReminderCallbackTestCase(TestCase):
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
    @classmethod
    def setUpClass(cls):
        cls.domain = "test"
        cls.case_type = "my_case_type"
        cls.message_1 = "Callback Message 1"
        cls.message_2 = "Callback Message 2"
        cls.handler = CaseReminderHandler(
            domain=cls.domain,
            case_type=cls.case_type,
            method="callback_test",
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
                   ,message={"en":cls.message_1}
                   ,callback_timeout_intervals=[]
                )
               ,CaseReminderEvent(
                    day_num = 0
                   ,fire_time = time(11,00,00)
                   ,message={"en":cls.message_2}
                   ,callback_timeout_intervals=[15,30]
                )
            ]
        )
        cls.handler.save()
        cls.user_id = "USER-ID-109349"
        cls.user = CommCareUser.create(cls.domain, 'chw.bob3', '****', uuid=cls.user_id)
        cls.user.user_data["time_zone"]="Africa/Nairobi"
        cls.user.save()
        cls.case = CommCareCase(
            domain=cls.domain,
            type=cls.case_type,
            user_id=cls.user_id
        )
        cls.case.save()
        cls.user.save_verified_number("test", "14445551234", True, None)

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
        
        # Create a callback
        c = CallLog(
            couch_recipient_doc_type    = "CommCareUser",
            couch_recipient             = self.user_id,
            phone_number                = "14445551234",
            direction                   = "I",
            date                        = datetime(year=2012, month=1, day=1, hour=8, minute=5)
        )
        c.save()
        
        # Day1, 11:15 timeout (should move on to next day)
        CaseReminderHandler.now = datetime(year=2012, month=1, day=1, hour=8, minute=15)
        CaseReminderHandler.fire_reminders()
        reminder = self.handler.get_reminder(self.case)
        self.assertNotEqual(reminder, None)
        self.assertEqual(reminder.next_fire, datetime(year=2012, month=1, day=2, hour=7, minute=0))
        self.assertEqual(reminder.schedule_iteration_num, 2)
        self.assertEqual(reminder.current_event_sequence_num, 0)
        self.assertEqual(reminder.last_fired, CaseReminderHandler.now)
        
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
        
        # Day2, 11:15 timeout (should move on to next timeout)
        CaseReminderHandler.now = datetime(year=2012, month=1, day=2, hour=8, minute=15)
        CaseReminderHandler.fire_reminders()
        reminder = self.handler.get_reminder(self.case)
        self.assertNotEqual(reminder, None)
        self.assertEqual(reminder.next_fire, datetime(year=2012, month=1, day=2, hour=8, minute=45))
        self.assertEqual(reminder.schedule_iteration_num, 2)
        self.assertEqual(reminder.current_event_sequence_num, 1)
        self.assertEqual(reminder.last_fired, CaseReminderHandler.now)
        
        # Day2, 11:45 timeout (should move on to next day)
        CaseReminderHandler.now = datetime(year=2012, month=1, day=2, hour=8, minute=45)
        CaseReminderHandler.fire_reminders()
        reminder = self.handler.get_reminder(self.case)
        self.assertNotEqual(reminder, None)
        self.assertEqual(reminder.next_fire, datetime(year=2012, month=1, day=3, hour=7, minute=0))
        self.assertEqual(reminder.schedule_iteration_num, 3)
        self.assertEqual(reminder.current_event_sequence_num, 0)
        self.assertEqual(reminder.last_fired, CaseReminderHandler.now)
        
        # Ensure that a missed call was logged
        missed_call_datetime = json_format_datetime(CaseReminderHandler.now)
        missed_call = EventLog.view("sms/event_by_domain_date_recipient",
                        key=["test", missed_call_datetime, "CommCareUser", self.user_id],
                        include_docs=True).one()
        self.assertNotEqual(missed_call, None)
        self.assertEqual(missed_call.event_type, MISSED_EXPECTED_CALLBACK)
        
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
        
        # Day3, 11:15 timeout (should move on to next timeout)
        CaseReminderHandler.now = datetime(year=2012, month=1, day=3, hour=8, minute=15)
        CaseReminderHandler.fire_reminders()
        reminder = self.handler.get_reminder(self.case)
        self.assertNotEqual(reminder, None)
        self.assertEqual(reminder.next_fire, datetime(year=2012, month=1, day=3, hour=8, minute=45))
        self.assertEqual(reminder.schedule_iteration_num, 3)
        self.assertEqual(reminder.current_event_sequence_num, 1)
        self.assertEqual(reminder.last_fired, CaseReminderHandler.now)
        
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

    @classmethod
    def tearDownClass(cls):
        pass


class CaseTypeReminderTestCase(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.domain = "test"
        cls.user_id = "USER-ID-109350"
        cls.user = CommCareUser.create(cls.domain, 'chw.bob4', '****', uuid=cls.user_id)
        
        cls.handler1 = CaseReminderHandler(
            domain=cls.domain,
            case_type="case_type_a",
            method="test",
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
        cls.handler1.save()
        
        cls.handler2 = CaseReminderHandler(
            domain=cls.domain,
            case_type="case_type_a",
            method="test",
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
        cls.handler2.save()
        
        cls.handler3 = CaseReminderHandler(
            domain=cls.domain,
            case_type="case_type_a",
            method="test",
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
        cls.handler3.save()
        
        cls.case1 = CommCareCase(
            domain=cls.domain,
            type="case_type_a",
            user_id=cls.user_id
        )
        cls.case1.save()
        
        cls.case2 = CommCareCase(
            domain=cls.domain,
            type="case_type_b",
            user_id=cls.user_id
        )
        cls.case2.save()

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

    @classmethod
    def tearDownClass(cls):
        pass

class StartConditionReminderTestCase(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.domain = "test"
        cls.user_id = "USER-ID-109351"
        cls.user = CommCareUser.create(cls.domain, 'chw.bob5', '****', uuid=cls.user_id)
        
        cls.handler1 = CaseReminderHandler(
            domain=cls.domain,
            case_type="case_type_a",
            method="test",
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
        cls.handler1.save()
        
        cls.case1 = CommCareCase(
            domain=cls.domain,
            type="case_type_a",
            user_id=cls.user_id
        )
        cls.case1.save()

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


    @classmethod
    def tearDownClass(cls):
        pass

class ReminderLockTestCase(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.domain = "test"
        cls.user_id = "USER-ID-109352"
        cls.user = CommCareUser.create(cls.domain, 'chw.bob6', '****', uuid=cls.user_id)
        
        cls.handler1 = CaseReminderHandler(
            domain=cls.domain,
            case_type="case_type_a",
            method="test",
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
        cls.handler1.save()
        
        cls.case1 = CommCareCase(
            domain=cls.domain,
            type="case_type_a",
            user_id=cls.user_id
        )
        cls.case1.save()

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

    @classmethod
    def tearDownClass(cls):
        pass


class MessageTestCase(TestCase):
    def test_message(self):
        message = 'The EDD for client with ID {case.external_id} is approaching in {case.edd.days_until} days.'
        case = {'external_id': 123, 'edd': datetime.utcnow() + timedelta(days=30)}
        outcome = 'The EDD for client with ID 123 is approaching in 30 days.'
        self.assertEqual(Message.render(message, case=case), outcome)
