import datetime
from corehq.apps.users.models import WebUser
from custom.ewsghana.reminders import WEB_REMINDER
from custom.ewsghana.reminders.web_user_reminder import WebUserReminder
from custom.ewsghana.utils import has_notifications_enabled


class VisitWebsiteReminder(WebUserReminder):

    def get_users(self):
        return WebUser.by_domain(self.domain)

    def recipients_filter(self, user):
        sql_location = user.get_sql_location(self.domain)
        if not sql_location or not sql_location.location_type.administrative:
            return False
        date = datetime.datetime.utcnow() - datetime.timedelta(weeks=13)
        return user.last_login < date and has_notifications_enabled(self.domain, user)

    def get_message(self, recipient):
        return WEB_REMINDER % {'name': recipient.full_name}
