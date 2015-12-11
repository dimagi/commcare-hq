from corehq.apps.locations.dbaccessors import get_web_users_by_location
from corehq.apps.locations.models import SQLLocation
from corehq.apps.reminders.util import get_preferred_phone_number_for_recipient
from corehq.apps.users.models import CommCareUser
from corehq.form_processor.interfaces.supply import SupplyInterface
from custom.ewsghana.reminders import THIRD_STOCK_ON_HAND_REMINDER, INCOMPLETE_SOH_TO_SUPER
from custom.ewsghana.reminders.const import DAYS_UNTIL_LATE
from custom.ewsghana.reminders.second_soh_reminder import SecondSOHReminder
from custom.ewsghana.utils import send_sms, has_notifications_enabled, report_status
from dimagi.utils.couch.database import iter_docs


class ThirdSOHReminder(SecondSOHReminder):

    def get_message_for_location(self, location):
        supply_point = SupplyInterface(location.domain).get_by_location(location)
        if not supply_point:
            return None, {}

        on_time_products, missing_products = report_status(location.sql_location, days_until_late=DAYS_UNTIL_LATE)

        if not on_time_products:
            return THIRD_STOCK_ON_HAND_REMINDER, {'facility': location.name}
        elif missing_products:
            products_names = ', '.join([
                product.name
                for product in missing_products
            ])

            return INCOMPLETE_SOH_TO_SUPER, {'facility': location.name, 'products': products_names}

        return None, {}

    def get_users_messages(self):
        locations = SQLLocation.active_objects.filter(domain=self.domain, location_type__administrative=False)
        for sql_location in locations:
            in_charges = map(CommCareUser.wrap, iter_docs(
                CommCareUser.get_db(),
                [in_charge.user_id for in_charge in sql_location.facilityincharge_set.all()]
            ))
            web_users = [
                web_user
                for web_user in get_web_users_by_location(self.domain, sql_location.location_id)
                if has_notifications_enabled(self.domain, web_user)
            ]
            message, kwargs = self.get_message_for_location(sql_location.couch_location)

            for user in web_users + in_charges:
                phone_number = get_preferred_phone_number_for_recipient(user)
                if not phone_number:
                    continue

                kwargs['name'] = user.full_name
                if message:
                    yield user, phone_number, message % kwargs

    def send(self):
        for user, phone_number, message in self.get_users_messages():
            send_sms(self.domain, user, phone_number, message)
