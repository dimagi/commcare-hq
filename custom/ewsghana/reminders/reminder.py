from corehq.apps.reminders.util import get_verified_number_for_recipient
from corehq.apps.sms.api import send_sms_to_verified_number
from corehq.apps.users.models import CommCareUser
from dimagi.utils.couch.database import iter_docs


class Reminder(object):

    def __init__(self, domain):
        self.domain = domain

    def recipients_filter(self, user):
        raise NotImplemented()

    def get_users(self):
        user_ids = CommCareUser.ids_by_domain(self.domain)
        for user_doc in iter_docs(CommCareUser.get_db(), user_ids):
            yield CommCareUser.wrap(user_doc)

    def get_recipients(self):
        for user in self.get_users():
            vn = get_verified_number_for_recipient(user)
            if vn and self.recipients_filter(user):
                yield vn

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
