import datetime
from corehq.apps.users.models import WebUser
from custom.ewsghana.reminders import WEB_REMINDER
from custom.ewsghana.reminders.reminder import Reminder


class VisitWebsiteReminder(Reminder):

    def get_users(self):
        return WebUser.by_domain(self.domain)

    def recipients_filter(self, user):
        sql_location = user.get_sql_location(self.domain)
        if not sql_location.location_type.administrative:
            return False
        date = datetime.datetime.utcnow() - datetime.timedelta(weeks=13)
        return user.last_login < date and user.user_data.get('sms_notifications', False)

    def get_message(self, recipient):
        return WEB_REMINDER % {'name': recipient.owner.full_name}
