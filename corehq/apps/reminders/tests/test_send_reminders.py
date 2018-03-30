from __future__ import absolute_import
from __future__ import unicode_literals
from casexml.apps.case.mock import CaseBlock
from casexml.apps.case.util import post_case_blocks
from corehq.apps.ivr.models import Call
from corehq.apps.reminders.models import (CaseReminderHandler, CaseReminder, MATCH_EXACT,
    MATCH_ANY_VALUE, MATCH_REGEX, EVENT_AS_OFFSET, EVENT_AS_SCHEDULE, CaseReminderEvent)
from corehq.apps.reminders.tests.utils import BaseReminderTestCase
from corehq.apps.sms.models import ExpectedCallback, CALLBACK_RECEIVED, CALLBACK_PENDING, CALLBACK_MISSED
from corehq.apps.users.models import CommCareUser
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors
from corehq.form_processor.tests.utils import run_with_all_backends
from corehq.util.test_utils import create_test_case, update_case
from datetime import datetime, date, time, timedelta
from django.test import TestCase


class ReminderTestCase(BaseReminderTestCase):
    """
    This is the original use case and tests a fixed reminder schedule.
    """

    def setUp(self):
        super(ReminderTestCase, self).setUp()
        self.domain = self.domain_obj.name
        self.case_type = "my_case_type"
        self.message = "Test reminder message."

        self.handler = (CaseReminderHandler.create(self.domain, 'test')
            .set_case_criteria_start_condition(self.case_type, 'start_sending', MATCH_EXACT, 'ok')
            .set_case_criteria_start_date(start_offset=1)
            .set_last_submitting_user_recipient()
            .set_sms_content_type('en')
            .set_schedule_manually(
                EVENT_AS_OFFSET,
                3,
                [
                    CaseReminderEvent(
                        day_num=0,
                        fire_time=time(0, 0),
                        message={'en': self.message},
                        callback_timeout_intervals=[]
                    ),
                ])
            .set_stop_condition(stop_case_property='stop_sending')
            .set_advanced_options()
        )
        self.handler.save()

        self.user = CommCareUser.create(self.domain, 'chw.bob', 'abc', phone_number='99912345')

    def tearDown(self):
        self.user.delete()
        super(ReminderTestCase, self).tearDown()

    @run_with_all_backends
    def test_ok(self):
        with create_test_case(self.domain, self.case_type, 'test-case', drop_signals=False,
                user_id=self.user.get_id) as case:

            self.assertIsNone(self.handler.get_reminder(case))

            # create reminder
            CaseReminderHandler.now = datetime(year=2011, month=7, day=7, hour=19, minute=8)
            update_case(self.domain, case.case_id, {'start_sending': 'ok'}, user_id=self.user.get_id)
            CaseReminderHandler.fire_reminders()
            reminder = self.handler.get_reminder(case)
            self.assertIsNotNone(reminder)
            self.assertEqual(
                reminder.next_fire,
                CaseReminderHandler.now + timedelta(days=self.handler.start_offset)
            )
            self.assertIsNone(reminder.last_fired)

            # fire a day after created
            CaseReminderHandler.now = datetime(year=2011, month=7, day=8, hour=19, minute=8)
            update_case(self.domain, case.case_id, {'irrelevant_1': 'ok'}, user_id=self.user.get_id)
            CaseReminderHandler.fire_reminders()
            reminder = self.handler.get_reminder(case)
            self.assertIsNotNone(reminder)
            self.assertEqual(
                reminder.next_fire,
                CaseReminderHandler.now + timedelta(days=self.handler.schedule_length)
            )
            self.assertEqual(reminder.last_fired, CaseReminderHandler.now)

            # Shouldn't fire until three days after created
            last_fired = CaseReminderHandler.now
            CaseReminderHandler.now = datetime(year=2011, month=7, day=9, hour=19, minute=8)
            CaseReminderHandler.fire_reminders()
            reminder = self.handler.get_reminder(case)
            self.assertIsNotNone(reminder)
            self.assertEqual(reminder.last_fired, last_fired)
            self.assertEqual(
                reminder.next_fire,
                last_fired + timedelta(days=self.handler.schedule_length)
            )

            # fire three days after last fired
            CaseReminderHandler.now = datetime(year=2011, month=7, day=11, hour=19, minute=8)
            update_case(self.domain, case.case_id, {'irrelevant_2': 'ok'}, user_id=self.user.get_id)
            CaseReminderHandler.fire_reminders()
            reminder = self.handler.get_reminder(case)
            self.assertIsNotNone(reminder)
            self.assertEqual(
                reminder.next_fire,
                CaseReminderHandler.now + timedelta(days=self.handler.schedule_length)
            )
            self.assertEqual(reminder.last_fired, CaseReminderHandler.now)

            # set stop_sending to 'ok' should make it stop sending and make the reminder inactive
            last_fired = CaseReminderHandler.now
            CaseReminderHandler.now = datetime(year=2011, month=7, day=14, hour=19, minute=8)
            update_case(self.domain, case.case_id, {'stop_sending': 'ok'}, user_id=self.user.get_id)
            CaseReminderHandler.fire_reminders()
            reminder = self.handler.get_reminder(case)
            self.assertIsNotNone(reminder)
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
        self.domain = self.domain_obj.name
        self.case_type = "my_case_type"
        self.message_1 = "Message 1"
        self.message_2 = "Message 2"
        self.message_3 = "Message 3"

        self.handler = (CaseReminderHandler.create(self.domain, 'test')
            .set_case_criteria_start_condition(self.case_type, 'start_sending', MATCH_ANY_VALUE)
            .set_case_criteria_start_date(start_offset=1)
            .set_last_submitting_user_recipient()
            .set_sms_content_type('en')
            .set_schedule_manually(
                EVENT_AS_SCHEDULE,
                7,
                [
                    CaseReminderEvent(
                        day_num=0,
                        fire_time=time(10, 0),
                        message={"en": self.message_1},
                        callback_timeout_intervals=[]
                    ),
                    CaseReminderEvent(
                        day_num=3,
                        fire_time=time(11, 0),
                        message={"en": self.message_2},
                        callback_timeout_intervals=[]
                    ),
                    CaseReminderEvent(
                        day_num=3,
                        fire_time=time(11, 30),
                        message={"en": self.message_3},
                        callback_timeout_intervals=[]
                    ),
                ])
            .set_stop_condition(max_iteration_count=2, stop_case_property='stop_sending')
            .set_advanced_options()
        )
        self.handler.save()

        self.user = CommCareUser.create(self.domain, 'chw.bob2', 'abc', phone_number='99912345')

    def tearDown(self):
        self.user.delete()
        super(ReminderIrregularScheduleTestCase, self).tearDown()

    @run_with_all_backends
    def test_ok(self):

        with create_test_case(self.domain, self.case_type, 'test-case', drop_signals=False,
                user_id=self.user.get_id) as case:

            self.assertIsNone(self.handler.get_reminder(case))

            # Spawn CaseReminder
            CaseReminderHandler.now = datetime(year=2012, month=1, day=1, hour=4, minute=0)
            update_case(self.domain, case.case_id, {'start_sending': 'ok'}, user_id=self.user.get_id)
            reminder = self.handler.get_reminder(case)
            self.assertIsNotNone(reminder)
            self.assertEqual(reminder.next_fire, datetime(year=2012, month=1, day=2, hour=10, minute=0))
            self.assertEqual(reminder.start_date, date(year=2012, month=1, day=1))
            self.assertEqual(reminder.schedule_iteration_num, 1)
            self.assertEqual(reminder.current_event_sequence_num, 0)
            self.assertEqual(reminder.last_fired, None)

            # Not yet the first fire time, nothing should happen
            CaseReminderHandler.now = datetime(year=2012, month=1, day=2, hour=9, minute=45)
            CaseReminderHandler.fire_reminders()
            reminder = self.handler.get_reminder(case)
            self.assertIsNotNone(reminder)
            self.assertEqual(reminder.next_fire, datetime(year=2012, month=1, day=2, hour=10, minute=0))
            self.assertEqual(reminder.schedule_iteration_num, 1)
            self.assertEqual(reminder.current_event_sequence_num, 0)
            self.assertEqual(reminder.last_fired, None)

            # Week1, Day1, 10:00 reminder
            CaseReminderHandler.now = datetime(year=2012, month=1, day=2, hour=10, minute=7)
            CaseReminderHandler.fire_reminders()
            reminder = self.handler.get_reminder(case)
            self.assertIsNotNone(reminder)
            self.assertEqual(reminder.next_fire, datetime(year=2012, month=1, day=5, hour=11, minute=0))
            self.assertEqual(reminder.schedule_iteration_num, 1)
            self.assertEqual(reminder.current_event_sequence_num, 1)
            self.assertEqual(reminder.last_fired, CaseReminderHandler.now)

            # Week1, Day4, 11:00 reminder
            CaseReminderHandler.now = datetime(year=2012, month=1, day=5, hour=11, minute=3)
            CaseReminderHandler.fire_reminders()
            reminder = self.handler.get_reminder(case)
            self.assertIsNotNone(reminder)
            self.assertEqual(reminder.next_fire, datetime(year=2012, month=1, day=5, hour=11, minute=30))
            self.assertEqual(reminder.schedule_iteration_num, 1)
            self.assertEqual(reminder.current_event_sequence_num, 2)
            self.assertEqual(reminder.last_fired, CaseReminderHandler.now)

            # Week1, Day4, 11:30 reminder
            CaseReminderHandler.now = datetime(year=2012, month=1, day=5, hour=11, minute=30)
            CaseReminderHandler.fire_reminders()
            reminder = self.handler.get_reminder(case)
            self.assertIsNotNone(reminder)
            self.assertEqual(reminder.next_fire, datetime(year=2012, month=1, day=9, hour=10, minute=0))
            self.assertEqual(reminder.schedule_iteration_num, 2)
            self.assertEqual(reminder.current_event_sequence_num, 0)
            self.assertEqual(reminder.last_fired, CaseReminderHandler.now)

            # Week2, Day1, 10:00 reminder
            CaseReminderHandler.now = datetime(year=2012, month=1, day=9, hour=10, minute=0)
            CaseReminderHandler.fire_reminders()
            reminder = self.handler.get_reminder(case)
            self.assertIsNotNone(reminder)
            self.assertEqual(reminder.next_fire, datetime(year=2012, month=1, day=12, hour=11, minute=0))
            self.assertEqual(reminder.schedule_iteration_num, 2)
            self.assertEqual(reminder.current_event_sequence_num, 1)
            self.assertEqual(reminder.last_fired, CaseReminderHandler.now)

            # Week2, Day4, 11:00 reminder
            CaseReminderHandler.now = datetime(year=2012, month=1, day=12, hour=11, minute=0)
            CaseReminderHandler.fire_reminders()
            reminder = self.handler.get_reminder(case)
            self.assertIsNotNone(reminder)
            self.assertEqual(reminder.next_fire, datetime(year=2012, month=1, day=12, hour=11, minute=30))
            self.assertEqual(reminder.schedule_iteration_num, 2)
            self.assertEqual(reminder.current_event_sequence_num, 2)
            self.assertEqual(reminder.last_fired, CaseReminderHandler.now)

            # Week2, Day4, 11:30 reminder
            CaseReminderHandler.now = datetime(year=2012, month=1, day=12, hour=11, minute=31)
            CaseReminderHandler.fire_reminders()
            reminder = self.handler.get_reminder(case)
            self.assertIsNotNone(reminder)
            self.assertEqual(reminder.schedule_iteration_num, 3)
            self.assertEqual(reminder.current_event_sequence_num, 0)
            self.assertEqual(reminder.last_fired, CaseReminderHandler.now)
            self.assertEqual(reminder.active, False)


class CaseTypeReminderTestCase(BaseReminderTestCase):

    def setUp(self):
        super(CaseTypeReminderTestCase, self).setUp()
        self.domain = self.domain_obj.name
        self.user = CommCareUser.create(self.domain, 'chw.bob4', 'abc', phone_number='99912345')

        self.handler1 = (CaseReminderHandler.create(self.domain, 'test')
            .set_case_criteria_start_condition('case_type_a', 'start_sending1', MATCH_ANY_VALUE)
            .set_case_criteria_start_date(start_offset=1)
            .set_last_submitting_user_recipient()
            .set_sms_content_type('en')
            .set_schedule_manually(
                EVENT_AS_OFFSET,
                3,
                [
                    CaseReminderEvent(
                        day_num=0,
                        fire_time=time(0, 0),
                        message={'en': 'Message1'},
                        callback_timeout_intervals=[]
                    ),
                ])
            .set_stop_condition(stop_case_property='stop_sending1')
            .set_advanced_options()
        )
        self.handler1.save()

        self.handler2 = (CaseReminderHandler.create(self.domain, 'test')
            .set_case_criteria_start_condition('case_type_a', 'start_sending2', MATCH_ANY_VALUE)
            .set_case_criteria_start_date(start_offset=2)
            .set_last_submitting_user_recipient()
            .set_sms_content_type('en')
            .set_schedule_manually(
                EVENT_AS_OFFSET,
                3,
                [
                    CaseReminderEvent(
                        day_num=0,
                        fire_time=time(0, 0),
                        message={'en': 'Message2'},
                        callback_timeout_intervals=[]
                    ),
                ])
            .set_stop_condition(stop_case_property='stop_sending2')
            .set_advanced_options()
        )
        self.handler2.save()

        self.handler3 = (CaseReminderHandler.create(self.domain, 'test')
            .set_case_criteria_start_condition('case_type_a', 'start_sending3', MATCH_ANY_VALUE)
            .set_case_criteria_start_date(start_offset=3)
            .set_last_submitting_user_recipient()
            .set_sms_content_type('en')
            .set_schedule_manually(
                EVENT_AS_OFFSET,
                3,
                [
                    CaseReminderEvent(
                        day_num=0,
                        fire_time=time(0, 0),
                        message={'en': 'Message3'},
                        callback_timeout_intervals=[]
                    ),
                ])
            .set_stop_condition(stop_case_property='stop_sending3')
            .set_advanced_options()
        )
        self.handler3.save()

    def tearDown(self):
        self.user.delete()
        super(CaseTypeReminderTestCase, self).tearDown()

    def create_case_1(self):
        return create_test_case(self.domain, 'case_type_a', 'test-case-1',
            drop_signals=False, user_id=self.user.get_id)

    def create_case_2(self):
        return create_test_case(self.domain, 'case_type_b', 'test-case-2',
            drop_signals=False, user_id=self.user.get_id)

    @run_with_all_backends
    def test_ok(self):
        with self.create_case_1() as case1, self.create_case_2() as case2:

            # Initial condition
            CaseReminderHandler.now = datetime(year=2012, month=2, day=16, hour=11, minute=0)
            update_case(self.domain, case1.case_id, {'start_sending1': 'ok', 'start_sending2': 'ok'},
                user_id=self.user.get_id)

            update_case(self.domain, case2.case_id, {'start_sending1': 'ok', 'start_sending3': 'ok'},
                user_id=self.user.get_id)

            self.assertIsNotNone(self.handler1.get_reminder(case1))
            self.assertIsNone(self.handler1.get_reminder(case2))
            self.assertIsNotNone(self.handler2.get_reminder(case1))
            self.assertIsNone(self.handler2.get_reminder(case2))
            self.assertIsNone(self.handler3.get_reminder(case1))
            self.assertIsNone(self.handler3.get_reminder(case2))

            self.assertEqual(
                self.handler1.get_reminder(case1).next_fire,
                CaseReminderHandler.now + timedelta(days=self.handler1.start_offset)
            )
            self.assertEqual(
                self.handler2.get_reminder(case1).next_fire,
                CaseReminderHandler.now + timedelta(days=self.handler2.start_offset)
            )


class StartConditionReminderTestCase(BaseReminderTestCase):

    def setUp(self):
        super(StartConditionReminderTestCase, self).setUp()
        self.domain = self.domain_obj.name
        self.user = CommCareUser.create(self.domain, 'chw.bob5', 'abc', phone_number='99912345')

        self.handler1 = (CaseReminderHandler.create(self.domain, 'test')
            .set_case_criteria_start_condition('case_type_a', 'start_sending1',
                MATCH_REGEX, '^(ok|\d\d\d\d-\d\d-\d\d)')
            .set_case_criteria_start_date(start_date='start_sending1', start_offset=1)
            .set_last_submitting_user_recipient()
            .set_sms_content_type('en')
            .set_schedule_manually(
                EVENT_AS_OFFSET,
                3,
                [
                    CaseReminderEvent(
                        day_num=0,
                        fire_time=time(0, 0),
                        message={'en': 'Message1'},
                        callback_timeout_intervals=[]
                    ),
                ])
            .set_stop_condition(stop_case_property='stop_sending1')
            .set_advanced_options(use_today_if_start_date_is_blank=True))
        self.handler1.save()

    def tearDown(self):
        self.user.delete()
        super(StartConditionReminderTestCase, self).tearDown()

    @run_with_all_backends
    def test_ok(self):
        with create_test_case(self.domain, 'case_type_a', 'test-case', drop_signals=False,
                user_id=self.user.get_id) as case:

            # Test changing a start condition which is a string
            # Spawn the reminder with an "ok" start condition value
            CaseReminderHandler.now = datetime(year=2012, month=2, day=17, hour=12, minute=0)
            self.assertIsNone(self.handler1.get_reminder(case))

            update_case(self.domain, case.case_id, {'start_sending1': 'ok'}, user_id=self.user.get_id)

            reminder = self.handler1.get_reminder(case)
            self.assertIsNotNone(reminder)
            self.assertEqual(
                reminder.next_fire,
                CaseReminderHandler.now + timedelta(days=self.handler1.start_offset)
            )

            # Test that saving the case without changing the start condition has no effect
            old_reminder_id = reminder.get_id
            update_case(self.domain, case.case_id, {'case_property1': 'abc'}, user_id=self.user.get_id)

            reminder = self.handler1.get_reminder(case)
            self.assertIsNotNone(reminder)
            self.assertEqual(reminder.get_id, old_reminder_id)

            # Test retiring the reminder
            old_reminder_id = reminder.get_id
            update_case(self.domain, case.case_id, {'start_sending1': ''}, user_id=self.user.get_id)

            self.assertIsNone(self.handler1.get_reminder(case))
            self.assertEqual(CaseReminder.get(old_reminder_id).doc_type, "CaseReminder-Deleted")

            # Test changing a start condition which is a date value
            # Spawn the reminder with date start condition value
            update_case(self.domain, case.case_id, {'start_sending1': '2012-02-20'}, user_id=self.user.get_id)

            reminder = self.handler1.get_reminder(case)
            self.assertIsNotNone(reminder)

            self.assertEqual(
                reminder.next_fire,
                datetime(2012, 2, 20) + timedelta(days=self.handler1.start_offset)
            )

            # Reset the date start condition
            old_reminder_id = reminder.get_id
            update_case(self.domain, case.case_id, {'start_sending1': '2012-02-22'}, user_id=self.user.get_id)

            reminder = self.handler1.get_reminder(case)
            self.assertIsNotNone(reminder)
            self.assertEqual(
                reminder.next_fire,
                datetime(2012, 2, 22) + timedelta(days=self.handler1.start_offset)
            )
            self.assertEqual(CaseReminder.get(old_reminder_id).doc_type, "CaseReminder-Deleted")

            # Test that saving the case without changing the start condition has no effect
            old_reminder_id = reminder.get_id
            update_case(self.domain, case.case_id, {'case_property1': 'abc'}, user_id=self.user.get_id)

            reminder = self.handler1.get_reminder(case)
            self.assertIsNotNone(reminder)
            self.assertEqual(reminder.get_id, old_reminder_id)

            # Retire the reminder
            old_reminder_id = reminder.get_id
            update_case(self.domain, case.case_id, {'start_sending1': ''}, user_id=self.user.get_id)

            reminder = self.handler1.get_reminder(case)
            self.assertIsNone(reminder)
            self.assertEqual(CaseReminder.get(old_reminder_id).doc_type, "CaseReminder-Deleted")

            # Test changing a start condition which is a string representation of a datetime value
            # Spawn the reminder with datetime start condition value
            update_case(self.domain, case.case_id, {'start_sending1': '2012-02-25 11:15'},
                user_id=self.user.get_id)

            reminder = self.handler1.get_reminder(case)
            self.assertIsNotNone(reminder)

            self.assertEqual(
                reminder.next_fire,
                datetime(2012, 2, 25, 11, 15) + timedelta(days=self.handler1.start_offset)
            )

            # Reset the datetime start condition
            old_reminder_id = reminder.get_id
            update_case(self.domain, case.case_id, {'start_sending1': '2012-02-26 11:20'},
                user_id=self.user.get_id)

            reminder = self.handler1.get_reminder(case)
            self.assertIsNotNone(reminder)

            self.assertEqual(
                reminder.next_fire,
                datetime(2012, 2, 26, 11, 20) + timedelta(days=self.handler1.start_offset)
            )
            self.assertEqual(CaseReminder.get(old_reminder_id).doc_type, "CaseReminder-Deleted")

            # Test that saving the case without changing the start condition has no effect
            old_reminder_id = reminder.get_id
            update_case(self.domain, case.case_id, {'case_property1': 'xyz'},
                user_id=self.user.get_id)

            reminder = self.handler1.get_reminder(case)
            self.assertIsNotNone(reminder)
            self.assertEqual(reminder.get_id, old_reminder_id)

            # Retire the reminder
            old_reminder_id = reminder.get_id
            update_case(self.domain, case.case_id, {'start_sending1': ''},
                user_id=self.user.get_id)

            reminder = self.handler1.get_reminder(case)
            self.assertIsNone(reminder)
            self.assertEqual(CaseReminder.get(old_reminder_id).doc_type, "CaseReminder-Deleted")


class ReminderDefinitionCalculationsTestCase(TestCase):

    def setUp(self):
        self.domain = 'reminder-calculation-test'

    @run_with_all_backends
    def test_calculate_start_date_without_today_option(self):
        now = datetime.utcnow()

        with create_test_case(self.domain, 'contact', 'test-case') as case:

            reminder = CaseReminderHandler(
                domain=self.domain,
                use_today_if_start_date_is_blank=False
            )
            self.assertEqual(
                reminder.get_case_criteria_reminder_start_date_info(case, now),
                (now, True, True)
            )

            reminder.start_date = 'start_date_case_property'
            self.assertEqual(
                reminder.get_case_criteria_reminder_start_date_info(case, now),
                (None, False, False)
            )

            update_case(self.domain, case.case_id, {'start_date_case_property': ''})
            case = CaseAccessors(self.domain).get_case(case.case_id)
            self.assertEqual(
                reminder.get_case_criteria_reminder_start_date_info(case, now),
                (None, False, False)
            )

            update_case(self.domain, case.case_id, {'start_date_case_property': '   '})
            case = CaseAccessors(self.domain).get_case(case.case_id)
            self.assertEqual(
                reminder.get_case_criteria_reminder_start_date_info(case, now),
                (None, False, False)
            )

            update_case(self.domain, case.case_id, {'start_date_case_property': 'abcdefg'})
            case = CaseAccessors(self.domain).get_case(case.case_id)
            self.assertEqual(
                reminder.get_case_criteria_reminder_start_date_info(case, now),
                (None, False, False)
            )

            update_case(self.domain, case.case_id, {'start_date_case_property': '2016-01-32'})
            case = CaseAccessors(self.domain).get_case(case.case_id)
            self.assertEqual(
                reminder.get_case_criteria_reminder_start_date_info(case, now),
                (None, False, False)
            )

            update_case(self.domain, case.case_id, {'start_date_case_property': '2016-01-10'})
            case = CaseAccessors(self.domain).get_case(case.case_id)
            self.assertEqual(
                reminder.get_case_criteria_reminder_start_date_info(case, now),
                (datetime(2016, 1, 10), True, False)
            )

            update_case(self.domain, case.case_id, {'start_date_case_property': '2016-01-12T00:00:00Z'})
            case = CaseAccessors(self.domain).get_case(case.case_id)
            self.assertEqual(
                reminder.get_case_criteria_reminder_start_date_info(case, now),
                (datetime(2016, 1, 12), True, False)
            )

    @run_with_all_backends
    def test_calculate_start_date_with_today_option(self):
        now = datetime.utcnow()

        with create_test_case(self.domain, 'contact', 'test-case') as case:

            reminder = CaseReminderHandler(
                domain=self.domain,
                use_today_if_start_date_is_blank=True
            )

            self.assertEqual(
                reminder.get_case_criteria_reminder_start_date_info(case, now),
                (now, True, True)
            )

            reminder.start_date = 'start_date_case_property'
            self.assertEqual(
                reminder.get_case_criteria_reminder_start_date_info(case, now),
                (now, True, True)
            )

            update_case(self.domain, case.case_id, {'start_date_case_property': ''})
            case = CaseAccessors(self.domain).get_case(case.case_id)
            self.assertEqual(
                reminder.get_case_criteria_reminder_start_date_info(case, now),
                (now, True, True)
            )

            update_case(self.domain, case.case_id, {'start_date_case_property': '   '})
            case = CaseAccessors(self.domain).get_case(case.case_id)
            self.assertEqual(
                reminder.get_case_criteria_reminder_start_date_info(case, now),
                (now, True, True)
            )

            update_case(self.domain, case.case_id, {'start_date_case_property': 'abcdefg'})
            case = CaseAccessors(self.domain).get_case(case.case_id)
            self.assertEqual(
                reminder.get_case_criteria_reminder_start_date_info(case, now),
                (now, True, True)
            )

            update_case(self.domain, case.case_id, {'start_date_case_property': '2016-01-32'})
            case = CaseAccessors(self.domain).get_case(case.case_id)
            self.assertEqual(
                reminder.get_case_criteria_reminder_start_date_info(case, now),
                (now, True, True)
            )

            update_case(self.domain, case.case_id, {'start_date_case_property': '2016-01-10'})
            case = CaseAccessors(self.domain).get_case(case.case_id)
            self.assertEqual(
                reminder.get_case_criteria_reminder_start_date_info(case, now),
                (datetime(2016, 1, 10), True, False)
            )

            update_case(self.domain, case.case_id, {'start_date_case_property': '2016-01-12T00:00:00Z'})
            case = CaseAccessors(self.domain).get_case(case.case_id)
            self.assertEqual(
                reminder.get_case_criteria_reminder_start_date_info(case, now),
                (datetime(2016, 1, 12), True, False)
            )
