from __future__ import absolute_import
from __future__ import unicode_literals
from corehq.apps.reminders.models import (CaseReminderHandler,
    REMINDER_TYPE_DEFAULT, REMINDER_TYPE_ONE_TIME)
from django.test import TestCase
from mock import patch


@patch('corehq.apps.reminders.models.CaseReminderHandler.check_state')
class ReminderCachingTestCase(TestCase):
    domain = 'reminder-cache-test'

    def tearDown(self):
        super(ReminderCachingTestCase, self).tearDown()
        CaseReminderHandler.get_handler_ids.clear(CaseReminderHandler, self.domain,
            reminder_type_filter=None)
        CaseReminderHandler.get_handler_ids.clear(CaseReminderHandler, self.domain,
            reminder_type_filter=REMINDER_TYPE_DEFAULT)
        CaseReminderHandler.get_handler_ids.clear(CaseReminderHandler, self.domain,
            reminder_type_filter=REMINDER_TYPE_ONE_TIME)

    def test_cache(self, check_state_mock):

        # Nothing expected at first
        self.assertEqual(
            CaseReminderHandler.get_handler_ids(self.domain),
            []
        )

        # Create two reminder definitions of different types
        handler1 = CaseReminderHandler(
            domain=self.domain,
            reminder_type=REMINDER_TYPE_DEFAULT,
        )
        handler1.save()
        self.addCleanup(handler1.delete)

        handler2 = CaseReminderHandler(
            domain=self.domain,
            reminder_type=REMINDER_TYPE_ONE_TIME,
        )
        handler2.save()
        self.addCleanup(handler2.delete)

        self.assertEqual(
            CaseReminderHandler.get_handler_ids(self.domain, reminder_type_filter=REMINDER_TYPE_DEFAULT),
            [handler1._id]
        )

        self.assertEqual(
            CaseReminderHandler.get_handler_ids(self.domain, reminder_type_filter=REMINDER_TYPE_ONE_TIME),
            [handler2._id]
        )

        self.assertEqual(
            sorted(CaseReminderHandler.get_handler_ids(self.domain)),
            sorted([handler1._id, handler2._id])
        )

        # Add another with default type
        handler3 = CaseReminderHandler(
            domain=self.domain,
            reminder_type=REMINDER_TYPE_DEFAULT,
        )
        handler3.save()
        self.addCleanup(handler3.delete)

        self.assertEqual(
            sorted(CaseReminderHandler.get_handler_ids(self.domain, reminder_type_filter=REMINDER_TYPE_DEFAULT)),
            sorted([handler1._id, handler3._id])
        )

        self.assertEqual(
            CaseReminderHandler.get_handler_ids(self.domain, reminder_type_filter=REMINDER_TYPE_ONE_TIME),
            [handler2._id]
        )

        self.assertEqual(
            sorted(CaseReminderHandler.get_handler_ids(self.domain)),
            sorted([handler1._id, handler2._id, handler3._id])
        )

        # Retire the one-time reminder
        handler2.retire()

        self.assertEqual(
            sorted(CaseReminderHandler.get_handler_ids(self.domain, reminder_type_filter=REMINDER_TYPE_DEFAULT)),
            sorted([handler1._id, handler3._id])
        )

        self.assertEqual(
            CaseReminderHandler.get_handler_ids(self.domain, reminder_type_filter=REMINDER_TYPE_ONE_TIME),
            []
        )

        self.assertEqual(
            sorted(CaseReminderHandler.get_handler_ids(self.domain)),
            sorted([handler1._id, handler3._id])
        )
