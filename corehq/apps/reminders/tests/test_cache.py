from corehq.apps.reminders.models import (CaseReminderHandler,
    REMINDER_TYPE_DEFAULT, REMINDER_TYPE_ONE_TIME)
from datetime import time
from django.test import TestCase
from mock import patch


@patch('corehq.apps.reminders.models.CaseReminderHandler.check_state')
class ReminderCachingTestCase(TestCase):

    def test_cache(self, check_state_mock):
        domain = 'reminder-cache-test'

        # Nothing expected at first
        self.assertEqual(
            CaseReminderHandler.get_handler_ids(domain),
            []
        )

        # Create two reminder definitions of different types
        handler1 = CaseReminderHandler(
            domain=domain,
            reminder_type=REMINDER_TYPE_DEFAULT,
        )
        handler1.save()

        handler2 = CaseReminderHandler(
            domain=domain,
            reminder_type=REMINDER_TYPE_ONE_TIME,
        )
        handler2.save()

        self.assertEqual(
            CaseReminderHandler.get_handler_ids(domain, reminder_type_filter=REMINDER_TYPE_DEFAULT),
            [handler1._id]
        )

        self.assertEqual(
            CaseReminderHandler.get_handler_ids(domain, reminder_type_filter=REMINDER_TYPE_ONE_TIME),
            [handler2._id]
        )

        self.assertEqual(
            sorted(CaseReminderHandler.get_handler_ids(domain)),
            sorted([handler1._id, handler2._id])
        )

        # Add another with default type
        handler3 = CaseReminderHandler(
            domain=domain,
            reminder_type=REMINDER_TYPE_DEFAULT,
        )
        handler3.save()

        self.assertEqual(
            sorted(CaseReminderHandler.get_handler_ids(domain, reminder_type_filter=REMINDER_TYPE_DEFAULT)),
            sorted([handler1._id, handler3._id])
        )

        self.assertEqual(
            CaseReminderHandler.get_handler_ids(domain, reminder_type_filter=REMINDER_TYPE_ONE_TIME),
            [handler2._id]
        )

        self.assertEqual(
            sorted(CaseReminderHandler.get_handler_ids(domain)),
            sorted([handler1._id, handler2._id, handler3._id])
        )

        # Retire the one-time reminder
        handler2.retire()

        self.assertEqual(
            sorted(CaseReminderHandler.get_handler_ids(domain, reminder_type_filter=REMINDER_TYPE_DEFAULT)),
            sorted([handler1._id, handler3._id])
        )

        self.assertEqual(
            CaseReminderHandler.get_handler_ids(domain, reminder_type_filter=REMINDER_TYPE_ONE_TIME),
            []
        )

        self.assertEqual(
            sorted(CaseReminderHandler.get_handler_ids(domain)),
            sorted([handler1._id, handler3._id])
        )

        handler1.delete()
        handler2.delete()
        handler3.delete()
