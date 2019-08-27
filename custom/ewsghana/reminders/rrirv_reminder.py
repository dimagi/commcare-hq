from custom.ewsghana.reminders import RRIRV_REMINDER
from custom.ewsghana.reminders.const import IN_CHARGE_ROLE
from custom.ewsghana.reminders.reminder import Reminder
from custom.ewsghana.reminders.utils import user_has_reporting_location


class RRIRVReminder(Reminder):

    def recipients_filter(self, user):
        roles = user.user_data.get('role', [])
        if not roles and not user_has_reporting_location(user):
            return False
        return any([role != IN_CHARGE_ROLE for role in user.user_data.get('role', [])])

    def get_message(self, recipient):
        return RRIRV_REMINDER % {'name': recipient.owner.full_name}
