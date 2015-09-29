from corehq.apps.locations.models import SQLLocation
from corehq.apps.users.models import CommCareUser
from custom.ewsghana.reminders.second_soh_reminder import SecondSOHReminder


class ThirdSOHReminder(SecondSOHReminder):

    def get_users_messages(self):
        for sql_location in SQLLocation.objects.filter(domain=self.domain, location_type__administrative=False):
            in_charges = sql_location.facilityincharge_set.all()
            message, kwargs = self.get_message_for_location(sql_location.couch_location)

            for in_charge in in_charges:
                user = CommCareUser.get_by_user_id(in_charge.user_id, self.domain)
                if not user.get_verified_number():
                    continue

                kwargs['name'] = user.name
                if message:
                    yield user.get_verified_number(), message % kwargs
