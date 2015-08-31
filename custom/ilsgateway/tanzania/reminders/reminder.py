from corehq.apps.locations.dbaccessors import get_users_by_location_id
from corehq.apps.locations.models import SQLLocation
from custom.ilsgateway.models import SupplyPointStatusValues, SupplyPointStatus
from custom.ilsgateway.tanzania.reminders import update_statuses
from custom.ilsgateway.utils import send_translated_message


class Reminder(object):

    status_value = None

    def __init__(self, domain, date, location_type='FACILITY'):
        self.domain = domain
        self.date = date
        self.location_type = location_type

    def get_message(self):
        raise NotImplemented()

    def get_status_type(self):
        raise NotImplemented()

    def location_filter(self, sql_location):
        raise NotImplemented()

    def get_sql_locations(self):
        return SQLLocation.objects.filter(location_type__name=self.location_type)

    def send(self):
        locations_ids = set()
        status_type = self.get_status_type()
        for sql_location in self.get_sql_locations():
            if not self.location_filter(sql_location):
                continue

            sent = None
            for user in self.get_location_users(sql_location):
                result = send_translated_message(user, self.get_message())
                if result:
                    sent = result

            if sent:
                locations_ids.add(sql_location.location_id)
        update_statuses(locations_ids, status_type, SupplyPointStatusValues.REMINDER_SENT)

    def get_location_users(self, sql_location):
        return get_users_by_location_id(self.domain, sql_location.location_id)


class GroupReminder(Reminder):

    @property
    def current_group(self):
        raise NotImplemented()

    def location_filter(self, sql_location):
        current_group = self.current_group
        location = sql_location.couch_location
        status_exists = SupplyPointStatus.objects.filter(
            location_id=sql_location.location_id,
            status_type=self.get_status_type(),
            status_date__gte=self.date
        ).exists()
        return (self.location_type == 'DISTRICT'
                or current_group in location.metadata.get('group', [])) and not status_exists
