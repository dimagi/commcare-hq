from __future__ import absolute_import
from custom.ewsghana.reminders import STOCK_ON_HAND_REMINDER
from custom.ewsghana.reminders.const import IN_CHARGE_ROLE
from custom.ewsghana.reminders.reminder import Reminder
from custom.ewsghana.utils import user_needs_reminders


class FirstSOHReminder(Reminder):

    def recipients_filter(self, user):
        roles = user.user_data.get('role', [])
        if not roles:
            return False

        return any([role != IN_CHARGE_ROLE for role in user.user_data.get('role', [])]) and \
            user_needs_reminders(user) and user.location_id

    def get_message(self, recipient):
        return STOCK_ON_HAND_REMINDER % {'name': recipient.owner.name}
