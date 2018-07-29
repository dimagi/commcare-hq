from __future__ import absolute_import
from __future__ import unicode_literals
from datetime import time
from django.test import TestCase
from corehq.apps.reminders.models import CaseReminderHandler, MATCH_EXACT, REPEAT_SCHEDULE_INDEFINITELY


class ReminderLookupsTest(TestCase):

    domain_1 = 'reminder-lookup-test-1'
    domain_2 = 'reminder-lookup-test-2'
    case_type_1 = 'case-type-1'
    case_type_2 = 'case-type-2'

    def _create_reminder(self, domain, case_type):
        reminder = (CaseReminderHandler
            .create(domain, 'test')
            .set_case_criteria_start_condition(case_type, 'status', MATCH_EXACT, 'green')
            .set_case_criteria_start_date()
            .set_case_recipient()
            .set_sms_content_type('en')
            .set_daily_schedule(fire_time=time(12, 0),
                message={'en': 'Hello {case.name}, your test result was normal.'})
            .set_stop_condition(max_iteration_count=REPEAT_SCHEDULE_INDEFINITELY)
            .set_advanced_options())
        reminder.save()
        return reminder

    def test_get_handler_ids_for_case_post_save(self):
        reminder1 = self._create_reminder(self.domain_1, self.case_type_1)
        reminder2 = self._create_reminder(self.domain_1, self.case_type_2)
        reminder3 = self._create_reminder(self.domain_2, self.case_type_1)
        self.addCleanup(reminder1.delete)
        self.addCleanup(reminder2.delete)
        self.addCleanup(reminder3.delete)

        self.assertEqual(
            CaseReminderHandler.get_handler_ids_for_case_post_save(self.domain_1, self.case_type_1),
            [reminder1._id]
        )

        self.assertEqual(
            CaseReminderHandler.get_handler_ids_for_case_post_save(self.domain_1, self.case_type_2),
            [reminder2._id]
        )

        self.assertEqual(
            CaseReminderHandler.get_handler_ids_for_case_post_save(self.domain_2, self.case_type_1),
            [reminder3._id]
        )

        # Test cache clear
        reminder4 = self._create_reminder(self.domain_1, self.case_type_1)
        self.addCleanup(reminder4.delete)

        result = CaseReminderHandler.get_handler_ids_for_case_post_save(self.domain_1, self.case_type_1)
        self.assertEqual(len(result), 2)
        self.assertEqual(
            set(result),
            set([reminder1._id, reminder4._id])
        )
