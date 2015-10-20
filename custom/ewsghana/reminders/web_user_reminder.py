from corehq.apps.reminders.util import get_preferred_phone_number_for_recipient
from custom.ewsghana.reminders.reminder import Reminder
from custom.ewsghana.utils import send_sms, has_notifications_enabled


class WebUserReminder(Reminder):

    def get_recipients(self):
        for user in self.get_users():
            if self.recipients_filter(user):
                yield user

    def send(self):
        for recipient, message in self.get_users_messages():
            phone_number = get_preferred_phone_number_for_recipient(recipient)
            if phone_number and has_notifications_enabled(self.domain, recipient):
                send_sms(self.domain, recipient, phone_number, message)
