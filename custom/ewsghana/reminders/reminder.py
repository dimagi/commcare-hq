from corehq.apps.sms.api import send_sms_to_verified_number
from corehq.apps.users.models import CommCareUser


class Reminder(object):

    def __init__(self, domain):
        self.domain = domain

    def recipients_filter(self, user):
        raise NotImplemented()

    def get_users(self):
        return CommCareUser.by_domain(self.domain)

    def get_recipients(self):
        for user in self.get_users():
            if user.get_verified_number() and self.recipients_filter(user):
                yield user.get_verified_number()

    def get_message(self, recipient):
        raise NotImplemented()

    def get_users_messages(self):
        for recipient in self.get_recipients():
            message = self.get_message(recipient)
            if message:
                yield recipient, self.get_message(recipient)

    def send(self):
        for recipient, message in self.get_users_messages():
            send_sms_to_verified_number(recipient, message)
