from corehq.apps.commtrack.models import SupplyPointCase
from custom.ewsghana.reminders import SECOND_STOCK_ON_HAND_REMINDER, SECOND_INCOMPLETE_SOH_REMINDER
from custom.ewsghana.reminders.const import IN_CHARGE_ROLE, DAYS_UNTIL_LATE
from custom.ewsghana.reminders.reminder import Reminder
from custom.ewsghana.reminders.utils import user_has_reporting_location
from custom.ewsghana.utils import report_status


class SecondSOHReminder(Reminder):

    def recipients_filter(self, user):
        roles = user.user_data.get('role', [])
        if not roles or not user.location:
            return False
        return any([role != IN_CHARGE_ROLE for role in user.user_data.get('role', [])])

    def get_message_for_location(self, location):
        supply_point = SupplyPointCase.get_by_location(location)
        if not supply_point:
            return

        on_time_products, missing_products = report_status(location.sql_location, days_until_late=DAYS_UNTIL_LATE)

        if not on_time_products:
            return SECOND_STOCK_ON_HAND_REMINDER, {}
        elif missing_products:
            products_names = ', '.join([
                product.name
                for product in missing_products
            ])

            return SECOND_INCOMPLETE_SOH_REMINDER, {'products': products_names}

        return None, {}

    def get_message(self, recipient):
        user = recipient.owner
        if not user_has_reporting_location(user) or not user.get_verified_number():
            return

        message, kwargs = self.get_message_for_location(user.location)
        if not message:
            return
        kwargs['name'] = user.name
        return message % kwargs
