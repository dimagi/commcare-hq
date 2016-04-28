from corehq.apps.hqcase.utils import update_case
from corehq.util.test_utils import set_parent_case
from corehq.apps.reminders.models import (CaseReminderHandler, CaseReminder, MATCH_EXACT,
    MATCH_REGEX, MATCH_ANY_VALUE, REPEAT_SCHEDULE_INDEFINITELY, FIRE_TIME_CASE_PROPERTY)
from corehq.form_processor.tests.utils import run_with_all_backends
from corehq.util.test_utils import create_test_case
from datetime import datetime, date, time
from django.test import TestCase
from mock import patch


class ReminderResponsivenessTest(TestCase):
    def setUp(self):
        self.domain = 'reminder-responsiveness-test'

    def get_reminders(self):
        return CaseReminder.view('reminders/by_domain_handler_case',
            start_key=[self.domain],
            end_key=[self.domain, {}],
            include_docs=True).all()

    def get_all_reminders(self):
        return CaseReminder.view('reminders/by_domain_handler_case',
            include_docs=True).all()

    def assertOneReminder(self):
        reminder_instances = self.get_reminders()
        self.assertEqual(len(reminder_instances), 1)
        return reminder_instances[0]

    @run_with_all_backends
    def test_case_property_match_equal(self):
        reminder = (CaseReminderHandler
            .create(self.domain, 'test')
            .set_case_criteria_start_condition('participant', 'status', MATCH_EXACT, 'green')
            .set_case_criteria_start_date()
            .set_case_recipient()
            .set_sms_content_type('en')
            .set_daily_schedule(fire_time=time(12, 0), message={'en': 'Hello {case.name}, your test result was normal.'})
            .set_stop_condition(max_iteration_count=REPEAT_SCHEDULE_INDEFINITELY)
            .set_advanced_options())
        reminder.save()

        self.assertEqual(self.get_reminders(), [])

        with create_test_case(self.domain, 'participant', 'bob', drop_signals=False) as case, \
                patch('corehq.apps.reminders.models.CaseReminderHandler.get_now') as now_mock:
            self.assertEqual(self.get_reminders(), [])

            now_mock.return_value = datetime(2016, 1, 1, 10, 0)
            update_case(self.domain, case.case_id, case_properties={'status': 'green'})

            reminder_instance = self.assertOneReminder()
            self.assertEqual(reminder_instance.domain, self.domain)
            self.assertEqual(reminder_instance.handler_id, reminder.get_id)
            self.assertTrue(reminder_instance.active)
            self.assertEqual(reminder_instance.start_date, date(2016, 1, 1))
            self.assertIsNone(reminder_instance.start_condition_datetime)
            self.assertEqual(reminder_instance.next_fire, datetime(2016, 1, 1, 12, 0))
            self.assertEqual(reminder_instance.case_id, case.case_id)
            self.assertEqual(reminder_instance.schedule_iteration_num, 1)
            self.assertEqual(reminder_instance.current_event_sequence_num, 0)

            update_case(self.domain, case.case_id, case_properties={'status': 'red'})
            self.assertEqual(self.get_reminders(), [])

    @run_with_all_backends
    def test_case_property_match_equal(self):
        reminder = (CaseReminderHandler
            .create(self.domain, 'test')
            .set_case_criteria_start_condition('participant', 'status', MATCH_EXACT, 'green')
            .set_case_criteria_start_date()
            .set_case_recipient()
            .set_sms_content_type('en')
            .set_daily_schedule(fire_time=time(12, 0), message={'en': 'Hello {case.name}, your test result was normal.'})
            .set_stop_condition(max_iteration_count=REPEAT_SCHEDULE_INDEFINITELY)
            .set_advanced_options())
        reminder.save()

        self.assertEqual(self.get_reminders(), [])

        with create_test_case(self.domain, 'participant', 'bob', drop_signals=False) as case, \
                patch('corehq.apps.reminders.models.CaseReminderHandler.get_now') as now_mock:
            self.assertEqual(self.get_reminders(), [])

            now_mock.return_value = datetime(2016, 1, 1, 10, 0)
            update_case(self.domain, case.case_id, case_properties={'status': 'green'})

            reminder_instance = self.assertOneReminder()
            self.assertEqual(reminder_instance.domain, self.domain)
            self.assertEqual(reminder_instance.case_id, case.case_id)
            self.assertEqual(reminder_instance.handler_id, reminder.get_id)
            self.assertIsNone(reminder_instance.user_id)
            self.assertEqual(reminder_instance.next_fire, datetime(2016, 1, 1, 12, 0))
            self.assertTrue(reminder_instance.active)
            self.assertEqual(reminder_instance.start_date, date(2016, 1, 1))
            self.assertEqual(reminder_instance.schedule_iteration_num, 1)
            self.assertEqual(reminder_instance.current_event_sequence_num, 0)
            self.assertEqual(reminder_instance.callback_try_count, 0)
            self.assertIsNone(reminder_instance.start_condition_datetime)

            update_case(self.domain, case.case_id, case_properties={'status': 'red'})
            self.assertEqual(self.get_reminders(), [])

    @run_with_all_backends
    def test_case_property_match_regex(self):
        reminder = (CaseReminderHandler
            .create(self.domain, 'test')
            .set_case_criteria_start_condition('participant', 'status', MATCH_REGEX, '^gr.+$')
            .set_case_criteria_start_date()
            .set_case_recipient()
            .set_sms_content_type('en')
            .set_daily_schedule(fire_time=time(12, 0), message={'en': 'Hello {case.name}, your test result was normal.'})
            .set_stop_condition(max_iteration_count=REPEAT_SCHEDULE_INDEFINITELY)
            .set_advanced_options())
        reminder.save()

        self.assertEqual(self.get_reminders(), [])

        with create_test_case(self.domain, 'participant', 'bob', drop_signals=False) as case, \
                patch('corehq.apps.reminders.models.CaseReminderHandler.get_now') as now_mock:
            self.assertEqual(self.get_reminders(), [])

            now_mock.return_value = datetime(2016, 1, 1, 10, 0)
            update_case(self.domain, case.case_id, case_properties={'status': 'gre'})

            reminder_instance = self.assertOneReminder()
            self.assertEqual(reminder_instance.domain, self.domain)
            self.assertEqual(reminder_instance.case_id, case.case_id)
            self.assertEqual(reminder_instance.handler_id, reminder.get_id)
            self.assertIsNone(reminder_instance.user_id)
            self.assertEqual(reminder_instance.next_fire, datetime(2016, 1, 1, 12, 0))
            self.assertTrue(reminder_instance.active)
            self.assertEqual(reminder_instance.start_date, date(2016, 1, 1))
            self.assertEqual(reminder_instance.schedule_iteration_num, 1)
            self.assertEqual(reminder_instance.current_event_sequence_num, 0)
            self.assertEqual(reminder_instance.callback_try_count, 0)
            self.assertIsNone(reminder_instance.start_condition_datetime)

            update_case(self.domain, case.case_id, case_properties={'status': 'red'})
            self.assertEqual(self.get_reminders(), [])

    @run_with_all_backends
    def test_case_property_match_any_value(self):
        reminder = (CaseReminderHandler
            .create(self.domain, 'test')
            .set_case_criteria_start_condition('participant', 'send_reminder', MATCH_ANY_VALUE)
            .set_case_criteria_start_date()
            .set_case_recipient()
            .set_sms_content_type('en')
            .set_daily_schedule(fire_time=time(12, 0), message={'en': 'Hello {case.name}, your test result was normal.'})
            .set_stop_condition(max_iteration_count=REPEAT_SCHEDULE_INDEFINITELY)
            .set_advanced_options())
        reminder.save()

        self.assertEqual(self.get_reminders(), [])

        with create_test_case(self.domain, 'participant', 'bob', drop_signals=False) as case, \
                patch('corehq.apps.reminders.models.CaseReminderHandler.get_now') as now_mock:
            self.assertEqual(self.get_reminders(), [])

            now_mock.return_value = datetime(2016, 1, 1, 10, 0)
            update_case(self.domain, case.case_id, case_properties={'send_reminder': 'y'})

            reminder_instance = self.assertOneReminder()
            self.assertEqual(reminder_instance.domain, self.domain)
            self.assertEqual(reminder_instance.case_id, case.case_id)
            self.assertEqual(reminder_instance.handler_id, reminder.get_id)
            self.assertIsNone(reminder_instance.user_id)
            self.assertEqual(reminder_instance.next_fire, datetime(2016, 1, 1, 12, 0))
            self.assertTrue(reminder_instance.active)
            self.assertEqual(reminder_instance.start_date, date(2016, 1, 1))
            self.assertEqual(reminder_instance.schedule_iteration_num, 1)
            self.assertEqual(reminder_instance.current_event_sequence_num, 0)
            self.assertEqual(reminder_instance.callback_try_count, 0)
            self.assertIsNone(reminder_instance.start_condition_datetime)

    @run_with_all_backends
    def test_case_property_start_date(self):
        reminder = (CaseReminderHandler
            .create(self.domain, 'test')
            .set_case_criteria_start_condition('participant', 'status', MATCH_EXACT, 'green')
            .set_case_criteria_start_date(start_date='start_date')
            .set_case_recipient()
            .set_sms_content_type('en')
            .set_daily_schedule(fire_time=time(12, 0), message={'en': 'Hello {case.name}, your test result was normal.'})
            .set_stop_condition(max_iteration_count=30)
            .set_advanced_options(use_today_if_start_date_is_blank=False))
        reminder.save()

        self.assertEqual(self.get_reminders(), [])

        with create_test_case(self.domain, 'participant', 'bob', drop_signals=False) as case, \
                patch('corehq.apps.reminders.models.CaseReminderHandler.get_now') as now_mock:
            self.assertEqual(self.get_reminders(), [])

            now_mock.return_value = datetime(2016, 1, 1, 10, 0)
            update_case(self.domain, case.case_id, case_properties={'status': 'green'})

            # start_date is blank, so should still be nothing
            self.assertEqual(self.get_reminders(), [])

            update_case(self.domain, case.case_id, case_properties={'start_date': '2016-01-08'})

            reminder_instance = self.assertOneReminder()
            self.assertEqual(reminder_instance.domain, self.domain)
            self.assertEqual(reminder_instance.case_id, case.case_id)
            self.assertEqual(reminder_instance.handler_id, reminder.get_id)
            self.assertIsNone(reminder_instance.user_id)
            self.assertEqual(reminder_instance.next_fire, datetime(2016, 1, 8, 12, 0))
            self.assertTrue(reminder_instance.active)
            self.assertEqual(reminder_instance.start_date, date(2016, 1, 8))
            self.assertEqual(reminder_instance.schedule_iteration_num, 1)
            self.assertEqual(reminder_instance.current_event_sequence_num, 0)
            self.assertEqual(reminder_instance.callback_try_count, 0)
            self.assertEqual(reminder_instance.start_condition_datetime, datetime(2016, 1, 8))

            # update start_date and the schedule should be recalculated
            update_case(self.domain, case.case_id, case_properties={'start_date': '2016-01-15'})

            reminder_instance = self.assertOneReminder()
            self.assertEqual(reminder_instance.domain, self.domain)
            self.assertEqual(reminder_instance.case_id, case.case_id)
            self.assertEqual(reminder_instance.handler_id, reminder.get_id)
            self.assertIsNone(reminder_instance.user_id)
            self.assertEqual(reminder_instance.next_fire, datetime(2016, 1, 15, 12, 0))
            self.assertTrue(reminder_instance.active)
            self.assertEqual(reminder_instance.start_date, date(2016, 1, 15))
            self.assertEqual(reminder_instance.schedule_iteration_num, 1)
            self.assertEqual(reminder_instance.current_event_sequence_num, 0)
            self.assertEqual(reminder_instance.callback_try_count, 0)
            self.assertEqual(reminder_instance.start_condition_datetime, datetime(2016, 1, 15))

            # update start_date to be in the past and the schedule should be recalculated and fast-forwarded
            update_case(self.domain, case.case_id, case_properties={'start_date': '2015-12-20'})

            reminder_instance = self.assertOneReminder()
            self.assertEqual(reminder_instance.domain, self.domain)
            self.assertEqual(reminder_instance.case_id, case.case_id)
            self.assertEqual(reminder_instance.handler_id, reminder.get_id)
            self.assertIsNone(reminder_instance.user_id)
            self.assertEqual(reminder_instance.next_fire, datetime(2016, 1, 1, 12, 0))
            self.assertTrue(reminder_instance.active)
            self.assertEqual(reminder_instance.start_date, date(2015, 12, 20))
            self.assertEqual(reminder_instance.schedule_iteration_num, 13)
            self.assertEqual(reminder_instance.current_event_sequence_num, 0)
            self.assertEqual(reminder_instance.callback_try_count, 0)
            self.assertEqual(reminder_instance.start_condition_datetime, datetime(2015, 12, 20))

            # update start_date to be further in the past and the reminder should be deactivated
            update_case(self.domain, case.case_id, case_properties={'start_date': '2015-12-01'})

            reminder_instance = self.assertOneReminder()
            self.assertEqual(reminder_instance.domain, self.domain)
            self.assertEqual(reminder_instance.case_id, case.case_id)
            self.assertEqual(reminder_instance.handler_id, reminder.get_id)
            self.assertIsNone(reminder_instance.user_id)
            self.assertEqual(reminder_instance.next_fire, datetime(2015, 12, 31, 12, 0))
            self.assertFalse(reminder_instance.active)
            self.assertEqual(reminder_instance.start_date, date(2015, 12, 1))
            self.assertEqual(reminder_instance.schedule_iteration_num, 31)
            self.assertEqual(reminder_instance.current_event_sequence_num, 0)
            self.assertEqual(reminder_instance.callback_try_count, 0)
            self.assertEqual(reminder_instance.start_condition_datetime, datetime(2015, 12, 1))

            # set start_date to be blank and the reminder should be deleted
            update_case(self.domain, case.case_id, case_properties={'start_date': ''})
            self.assertEqual(self.get_reminders(), [])

    @run_with_all_backends
    def test_case_property_start_date_with_blank_option(self):
        reminder = (CaseReminderHandler
            .create(self.domain, 'test')
            .set_case_criteria_start_condition('participant', 'status', MATCH_EXACT, 'green')
            .set_case_criteria_start_date(start_date='start_date')
            .set_case_recipient()
            .set_sms_content_type('en')
            .set_daily_schedule(fire_time=time(12, 0), message={'en': 'Hello {case.name}, your test result was normal.'})
            .set_stop_condition(max_iteration_count=30)
            .set_advanced_options(use_today_if_start_date_is_blank=True))
        reminder.save()

        self.assertEqual(self.get_reminders(), [])

        with create_test_case(self.domain, 'participant', 'bob', drop_signals=False) as case, \
                patch('corehq.apps.reminders.models.CaseReminderHandler.get_now') as now_mock:
            self.assertEqual(self.get_reminders(), [])

            now_mock.return_value = datetime(2016, 1, 1, 10, 0)

            # start_date is blank, but reminder should be spawned using today's value
            update_case(self.domain, case.case_id, case_properties={'status': 'green'})

            reminder_instance = self.assertOneReminder()
            self.assertEqual(reminder_instance.domain, self.domain)
            self.assertEqual(reminder_instance.case_id, case.case_id)
            self.assertEqual(reminder_instance.handler_id, reminder.get_id)
            self.assertIsNone(reminder_instance.user_id)
            self.assertEqual(reminder_instance.next_fire, datetime(2016, 1, 1, 12, 0))
            self.assertTrue(reminder_instance.active)
            self.assertEqual(reminder_instance.start_date, date(2016, 1, 1))
            self.assertEqual(reminder_instance.schedule_iteration_num, 1)
            self.assertEqual(reminder_instance.current_event_sequence_num, 0)
            self.assertEqual(reminder_instance.callback_try_count, 0)
            self.assertIsNone(reminder_instance.start_condition_datetime)

            # update start_date and the schedule should be recalculated
            update_case(self.domain, case.case_id, case_properties={'start_date': '2016-01-08'})

            reminder_instance = self.assertOneReminder()
            self.assertEqual(reminder_instance.domain, self.domain)
            self.assertEqual(reminder_instance.case_id, case.case_id)
            self.assertEqual(reminder_instance.handler_id, reminder.get_id)
            self.assertIsNone(reminder_instance.user_id)
            self.assertEqual(reminder_instance.next_fire, datetime(2016, 1, 8, 12, 0))
            self.assertTrue(reminder_instance.active)
            self.assertEqual(reminder_instance.start_date, date(2016, 1, 8))
            self.assertEqual(reminder_instance.schedule_iteration_num, 1)
            self.assertEqual(reminder_instance.current_event_sequence_num, 0)
            self.assertEqual(reminder_instance.callback_try_count, 0)
            self.assertEqual(reminder_instance.start_condition_datetime, datetime(2016, 1, 8))

            # update start_date to be in the past and the schedule should be recalculated and fast-forwarded
            update_case(self.domain, case.case_id, case_properties={'start_date': '2015-12-20'})

            reminder_instance = self.assertOneReminder()
            self.assertEqual(reminder_instance.domain, self.domain)
            self.assertEqual(reminder_instance.case_id, case.case_id)
            self.assertEqual(reminder_instance.handler_id, reminder.get_id)
            self.assertIsNone(reminder_instance.user_id)
            self.assertEqual(reminder_instance.next_fire, datetime(2016, 1, 1, 12, 0))
            self.assertTrue(reminder_instance.active)
            self.assertEqual(reminder_instance.start_date, date(2015, 12, 20))
            self.assertEqual(reminder_instance.schedule_iteration_num, 13)
            self.assertEqual(reminder_instance.current_event_sequence_num, 0)
            self.assertEqual(reminder_instance.callback_try_count, 0)
            self.assertEqual(reminder_instance.start_condition_datetime, datetime(2015, 12, 20))

            # update start_date to be further in the past and the reminder should be deactivated
            update_case(self.domain, case.case_id, case_properties={'start_date': '2015-12-01'})

            reminder_instance = self.assertOneReminder()
            self.assertEqual(reminder_instance.domain, self.domain)
            self.assertEqual(reminder_instance.case_id, case.case_id)
            self.assertEqual(reminder_instance.handler_id, reminder.get_id)
            self.assertIsNone(reminder_instance.user_id)
            self.assertEqual(reminder_instance.next_fire, datetime(2015, 12, 31, 12, 0))
            self.assertFalse(reminder_instance.active)
            self.assertEqual(reminder_instance.start_date, date(2015, 12, 1))
            self.assertEqual(reminder_instance.schedule_iteration_num, 31)
            self.assertEqual(reminder_instance.current_event_sequence_num, 0)
            self.assertEqual(reminder_instance.callback_try_count, 0)
            self.assertEqual(reminder_instance.start_condition_datetime, datetime(2015, 12, 1))

            # set start_date to be blank and the reminder should go back to using today as start date
            update_case(self.domain, case.case_id, case_properties={'start_date': ''})

            reminder_instance = self.assertOneReminder()
            self.assertEqual(reminder_instance.domain, self.domain)
            self.assertEqual(reminder_instance.case_id, case.case_id)
            self.assertEqual(reminder_instance.handler_id, reminder.get_id)
            self.assertIsNone(reminder_instance.user_id)
            self.assertEqual(reminder_instance.next_fire, datetime(2016, 1, 1, 12, 0))
            self.assertTrue(reminder_instance.active)
            self.assertEqual(reminder_instance.start_date, date(2016, 1, 1))
            self.assertEqual(reminder_instance.schedule_iteration_num, 1)
            self.assertEqual(reminder_instance.current_event_sequence_num, 0)
            self.assertEqual(reminder_instance.callback_try_count, 0)
            self.assertIsNone(reminder_instance.start_condition_datetime)

    @run_with_all_backends
    def test_case_type_match(self):
        reminder = (CaseReminderHandler
            .create(self.domain, 'test')
            .set_case_criteria_start_condition('participant', 'status', MATCH_EXACT, 'green')
            .set_case_criteria_start_date()
            .set_case_recipient()
            .set_sms_content_type('en')
            .set_daily_schedule(fire_time=time(12, 0), message={'en': 'Hello {case.name}, your test result was normal.'})
            .set_stop_condition(max_iteration_count=REPEAT_SCHEDULE_INDEFINITELY)
            .set_advanced_options())
        reminder.save()

        self.assertEqual(self.get_reminders(), [])

        with create_test_case(self.domain, 'ex-participant', 'bob', drop_signals=False) as case, \
                patch('corehq.apps.reminders.models.CaseReminderHandler.get_now') as now_mock:
            self.assertEqual(self.get_reminders(), [])

            now_mock.return_value = datetime(2016, 1, 1, 10, 0)
            update_case(self.domain, case.case_id, case_properties={'status': 'green'})
            self.assertEqual(self.get_reminders(), [])

            reminder.set_case_criteria_start_condition('ex-participant', 'status', MATCH_EXACT, 'green')
            reminder.save()

            reminder_instance = self.assertOneReminder()
            self.assertEqual(reminder_instance.domain, self.domain)
            self.assertEqual(reminder_instance.handler_id, reminder.get_id)
            self.assertTrue(reminder_instance.active)
            self.assertEqual(reminder_instance.start_date, date(2016, 1, 1))
            self.assertIsNone(reminder_instance.start_condition_datetime)
            self.assertEqual(reminder_instance.next_fire, datetime(2016, 1, 1, 12, 0))
            self.assertEqual(reminder_instance.case_id, case.case_id)
            self.assertEqual(reminder_instance.schedule_iteration_num, 1)
            self.assertEqual(reminder_instance.current_event_sequence_num, 0)

            reminder.set_case_criteria_start_condition('participant', 'status', MATCH_EXACT, 'green')
            reminder.save()
            self.assertEqual(self.get_reminders(), [])

    @run_with_all_backends
    def test_parent_case_property_criteria(self):
        reminder = (CaseReminderHandler
            .create(self.domain, 'test')
            .set_case_criteria_start_condition('participant', 'parent/status', MATCH_EXACT, 'green')
            .set_case_criteria_start_date()
            .set_case_recipient()
            .set_sms_content_type('en')
            .set_daily_schedule(fire_time=time(12, 0), message={'en': 'Hello {case.name}, your test result was normal.'})
            .set_stop_condition(max_iteration_count=REPEAT_SCHEDULE_INDEFINITELY)
            .set_advanced_options())
        reminder.save()

        self.assertEqual(self.get_reminders(), [])

        with create_test_case(self.domain, 'participant', 'bob', drop_signals=False) as child_case, \
                create_test_case(self.domain, 'parent-case', 'jim', drop_signals=False) as parent_case, \
                patch('corehq.apps.reminders.models.CaseReminderHandler.get_now') as now_mock:
            self.assertEqual(self.get_reminders(), [])

            set_parent_case(self.domain, child_case, parent_case)
            self.assertEqual(self.get_reminders(), [])

            now_mock.return_value = datetime(2016, 1, 1, 10, 0)
            update_case(self.domain, child_case.case_id, case_properties={'status': 'green'})
            self.assertEqual(self.get_reminders(), [])

            update_case(self.domain, child_case.case_id, case_properties={'status': ''})
            self.assertEqual(self.get_reminders(), [])

            update_case(self.domain, parent_case.case_id, case_properties={'status': 'green'})
            reminder_instance = self.assertOneReminder()
            self.assertEqual(reminder_instance.domain, self.domain)
            self.assertEqual(reminder_instance.handler_id, reminder.get_id)
            self.assertTrue(reminder_instance.active)
            self.assertEqual(reminder_instance.start_date, date(2016, 1, 1))
            self.assertIsNone(reminder_instance.start_condition_datetime)
            self.assertEqual(reminder_instance.next_fire, datetime(2016, 1, 1, 12, 0))
            self.assertEqual(reminder_instance.case_id, child_case.case_id)
            self.assertEqual(reminder_instance.schedule_iteration_num, 1)
            self.assertEqual(reminder_instance.current_event_sequence_num, 0)

            update_case(self.domain, parent_case.case_id, case_properties={'status': 'red'})
            self.assertEqual(self.get_reminders(), [])

    @run_with_all_backends
    def test_reminder_delete(self):
        reminder = (CaseReminderHandler
            .create(self.domain, 'test')
            .set_case_criteria_start_condition('participant', 'status', MATCH_EXACT, 'green')
            .set_case_criteria_start_date()
            .set_case_recipient()
            .set_sms_content_type('en')
            .set_daily_schedule(fire_time=time(12, 0), message={'en': 'Hello {case.name}, your test result was normal.'})
            .set_stop_condition(max_iteration_count=REPEAT_SCHEDULE_INDEFINITELY)
            .set_advanced_options())
        reminder.save()

        r1 = CaseReminder(domain=self.domain, handler_id=reminder.get_id)
        r2 = CaseReminder(domain=self.domain, handler_id='abc')
        r3 = CaseReminder(domain='def', handler_id='ghi')

        r1.save()
        r2.save()
        r3.save()

        self.assertEqual(len(self.get_all_reminders()), 3)
        reminder.retire()
        self.assertEqual(len(self.get_all_reminders()), 2)

        r1 = CaseReminder.get(r1.get_id)
        r2 = CaseReminder.get(r2.get_id)
        r3 = CaseReminder.get(r3.get_id)

        self.assertEqual(r1.doc_type, 'CaseReminder-Deleted')
        self.assertEqual(r2.doc_type, 'CaseReminder')
        self.assertEqual(r3.doc_type, 'CaseReminder')

    @run_with_all_backends
    def test_case_property_reminder_time(self):
        reminder = (CaseReminderHandler
            .create(self.domain, 'test')
            .set_case_criteria_start_condition('participant', 'status', MATCH_EXACT, 'green')
            .set_case_criteria_start_date()
            .set_case_recipient()
            .set_sms_content_type('en')
            .set_daily_schedule(fire_time='preferred_time', fire_time_type=FIRE_TIME_CASE_PROPERTY,
                message={'en': 'Hello {case.name}, your test result was normal.'})
            .set_stop_condition(max_iteration_count=REPEAT_SCHEDULE_INDEFINITELY)
            .set_advanced_options())
        reminder.save()

        self.assertEqual(self.get_reminders(), [])

        with create_test_case(self.domain, 'participant', 'bob', drop_signals=False) as case, \
                patch('corehq.apps.reminders.models.CaseReminderHandler.get_now') as now_mock:
            self.assertEqual(self.get_reminders(), [])

            now_mock.return_value = datetime(2016, 1, 1, 10, 0)
            update_case(self.domain, case.case_id, case_properties={'status': 'green', 'preferred_time': '14:00:00'})

            reminder_instance = self.assertOneReminder()
            self.assertEqual(reminder_instance.domain, self.domain)
            self.assertEqual(reminder_instance.handler_id, reminder.get_id)
            self.assertTrue(reminder_instance.active)
            self.assertEqual(reminder_instance.start_date, date(2016, 1, 1))
            self.assertIsNone(reminder_instance.start_condition_datetime)
            self.assertEqual(reminder_instance.next_fire, datetime(2016, 1, 1, 14, 0))
            self.assertEqual(reminder_instance.case_id, case.case_id)
            self.assertEqual(reminder_instance.schedule_iteration_num, 1)
            self.assertEqual(reminder_instance.current_event_sequence_num, 0)

    @run_with_all_backends
    def test_case_property_reminder_time_default(self):
        reminder = (CaseReminderHandler
            .create(self.domain, 'test')
            .set_case_criteria_start_condition('participant', 'status', MATCH_EXACT, 'green')
            .set_case_criteria_start_date()
            .set_case_recipient()
            .set_sms_content_type('en')
            .set_daily_schedule(fire_time='preferred_time', fire_time_type=FIRE_TIME_CASE_PROPERTY,
                message={'en': 'Hello {case.name}, your test result was normal.'})
            .set_stop_condition(max_iteration_count=REPEAT_SCHEDULE_INDEFINITELY)
            .set_advanced_options())
        reminder.save()

        self.assertEqual(self.get_reminders(), [])

        with create_test_case(self.domain, 'participant', 'bob', drop_signals=False) as case, \
                patch('corehq.apps.reminders.models.CaseReminderHandler.get_now') as now_mock:
            self.assertEqual(self.get_reminders(), [])

            now_mock.return_value = datetime(2016, 1, 1, 10, 0)
            update_case(self.domain, case.case_id, case_properties={'status': 'green'})

            reminder_instance = self.assertOneReminder()
            self.assertEqual(reminder_instance.domain, self.domain)
            self.assertEqual(reminder_instance.handler_id, reminder.get_id)
            self.assertTrue(reminder_instance.active)
            self.assertEqual(reminder_instance.start_date, date(2016, 1, 1))
            self.assertIsNone(reminder_instance.start_condition_datetime)
            self.assertEqual(reminder_instance.next_fire, datetime(2016, 1, 1, 12, 0))
            self.assertEqual(reminder_instance.case_id, case.case_id)
            self.assertEqual(reminder_instance.schedule_iteration_num, 1)
            self.assertEqual(reminder_instance.current_event_sequence_num, 0)

    @run_with_all_backends
    def test_case_time_zone(self):
        reminder = (CaseReminderHandler
            .create(self.domain, 'test')
            .set_case_criteria_start_condition('participant', 'status', MATCH_EXACT, 'green')
            .set_case_criteria_start_date()
            .set_case_recipient()
            .set_sms_content_type('en')
            .set_daily_schedule(fire_time=time(12, 0), message={'en': 'Hello {case.name}, your test result was normal.'})
            .set_stop_condition(max_iteration_count=REPEAT_SCHEDULE_INDEFINITELY)
            .set_advanced_options())
        reminder.save()

        self.assertEqual(self.get_reminders(), [])

        with create_test_case(self.domain, 'participant', 'bob', drop_signals=False) as case, \
                patch('corehq.apps.reminders.models.CaseReminderHandler.get_now') as now_mock:
            self.assertEqual(self.get_reminders(), [])

            now_mock.return_value = datetime(2016, 1, 1, 10, 0)
            update_case(self.domain, case.case_id, case_properties={'status': 'green', 'time_zone': 'America/New_York'})

            reminder_instance = self.assertOneReminder()
            self.assertEqual(reminder_instance.domain, self.domain)
            self.assertEqual(reminder_instance.handler_id, reminder.get_id)
            self.assertTrue(reminder_instance.active)
            self.assertEqual(reminder_instance.start_date, date(2016, 1, 1))
            self.assertIsNone(reminder_instance.start_condition_datetime)
            self.assertEqual(reminder_instance.next_fire, datetime(2016, 1, 1, 17, 0))
            self.assertEqual(reminder_instance.case_id, case.case_id)
            self.assertEqual(reminder_instance.schedule_iteration_num, 1)
            self.assertEqual(reminder_instance.current_event_sequence_num, 0)

    def tearDown(self):
        for reminder_instance in self.get_all_reminders():
            reminder_instance.delete()
        for reminder in CaseReminderHandler.get_handlers(self.domain):
            reminder.delete()
