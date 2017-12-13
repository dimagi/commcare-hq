from __future__ import absolute_import
from corehq.apps.users.models import CommCareUser
from custom.ewsghana.handlers import (STOP_MESSAGE, START_MESSAGE,
    DEACTIVATE_REMINDERS, REACTIVATE_REMINDERS)
from custom.ewsghana.tests.handlers.utils import EWSScriptTest


class TestReminderOnOffHandler(EWSScriptTest):

    def assertNeedsRemindersFalse(self):
        user = CommCareUser.get(self.user1.get_id)
        self.assertEqual(user.user_data['needs_reminders'], 'False')

    def assertNeedsRemindersTrue(self):
        user = CommCareUser.get(self.user1.get_id)
        self.assertEqual(user.user_data['needs_reminders'], 'True')

    def test_reminder_on_off(self):
        self.assertFalse('needs_reminders' in self.user1.user_data)

        # needs_reminders is blank; test help message both ways
        self.run_script(
            """
            5551234 > help reminder
            5551234 < {}
            """.format(REACTIVATE_REMINDERS)
        )

        self.run_script(
            """
            5551234 > reminder
            5551234 < {}
            """.format(REACTIVATE_REMINDERS)
        )

        # activate reminders
        self.run_script(
            """
            5551234 > reminder on
            5551234 < {}
            """.format(START_MESSAGE)
        )
        self.assertNeedsRemindersTrue()

        # needs_reminders is "True"; test help message both ways
        self.run_script(
            """
            5551234 > help reminder
            5551234 < {}
            """.format(DEACTIVATE_REMINDERS)
        )

        self.run_script(
            """
            5551234 > reminder
            5551234 < {}
            """.format(DEACTIVATE_REMINDERS)
        )

        # deactivate reminders
        self.run_script(
            """
            5551234 > reminder off
            5551234 < {}
            """.format(STOP_MESSAGE)
        )
        self.assertNeedsRemindersFalse()

        # needs_reminders is "False"; test help message both ways
        self.run_script(
            """
            5551234 > help reminder
            5551234 < {}
            """.format(REACTIVATE_REMINDERS)
        )

        self.run_script(
            """
            5551234 > reminder
            5551234 < {}
            """.format(REACTIVATE_REMINDERS)
        )
