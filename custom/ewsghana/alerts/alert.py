from datetime import datetime
from corehq.apps.locations.dbaccessors import get_web_users_by_location
from corehq.apps.reminders.util import get_preferred_phone_number_for_recipient
from custom.ewsghana.models import SQLNotification
from custom.ewsghana.utils import send_sms, has_notifications_enabled


class Notification(object):

    def __init__(self, domain, user, message):
        self.domain = domain
        self.user = user
        self.message = message

    def send(self):
        phone_number = get_preferred_phone_number_for_recipient(self.user)
        if phone_number and has_notifications_enabled(self.domain, self.user):
            send_sms(self.domain, self.user, phone_number, self.message)


class Alert(object):

    message = None

    def __init__(self, domain):
        self.domain = domain

    def get_sql_locations(self):
        raise NotImplemented()

    def get_users(self, sql_location):
        return [
            user
            for user in get_web_users_by_location(self.domain, sql_location.location_id)
            if get_preferred_phone_number_for_recipient(user)
        ]

    def filter_user(self, user):
        raise NotImplemented()

    def program_clause(self, user_program, programs):
        raise NotImplemented()

    def get_message(self, user, data):
        program_id = user.get_domain_membership(self.domain).program_id
        locations = []
        for location_name, programs in data.items():
            if self.program_clause(program_id, programs):
                locations.append(location_name)
        if not locations:
            return
        return self.message % ', '.join(sorted(locations))

    def get_data(self, sql_location):
        raise NotImplemented()

    def get_notifications(self):
        for sql_location in self.get_sql_locations():
            data = self.get_data(sql_location)

            for user in self.get_users(sql_location):
                message = self.get_message(user, data)

                if message:
                    yield Notification(self.domain, user, message)

    def send(self):
        for notification in self.get_notifications():
            notification.send()


class WeeklyAlert(Alert):

    def send(self):
        for notification in self.get_notifications():
            year, week, _ = datetime.utcnow().isocalendar()
            sql_notification, created = SQLNotification.objects.get_or_create(
                domain=self.domain,
                user_id=notification.user.get_id,
                type=self.__class__.__name__,
                week=week,
                year=year
            )
            if created:
                notification.send()
