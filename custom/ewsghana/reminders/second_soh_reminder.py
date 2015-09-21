import datetime
from corehq.apps.commtrack.models import SupplyPointCase, StockState
from custom.ewsghana.reminders import SECOND_STOCK_ON_HAND_REMINDER, SECOND_INCOMPLETE_SOH_REMINDER
from custom.ewsghana.reminders.const import DAYS_UNTIL_LATE, IN_CHARGE_ROLE
from custom.ewsghana.reminders.reminder import Reminder
from custom.ewsghana.reminders.utils import user_has_reporting_location


class SecondSOHReminder(Reminder):

    def recipients_filter(self, user):
        roles = user.user_data.get('role', [])
        if not roles or not user.location:
            return False
        return any([role != IN_CHARGE_ROLE for role in user.user_data.get('role', [])])

    def get_message_for_location(self, location):
        now = datetime.datetime.utcnow()
        date = now - datetime.timedelta(days=DAYS_UNTIL_LATE)
        supply_point = SupplyPointCase.get_by_location(location)
        if not supply_point:
            return

        stock_states = StockState.objects.filter(
            case_id=supply_point.get_id,
            last_modified_date__gte=date
        )
        products = location.sql_location.products
        location_products_ids = [product.product_id for product in products]
        reported_products_ids = [stock_state.product_id for stock_state in stock_states]
        missing_products_ids = set(location_products_ids) - set(reported_products_ids)

        if not stock_states:
            return SECOND_STOCK_ON_HAND_REMINDER, {}
        elif missing_products_ids:
            products_names = ', '.join([
                product.name
                for product in products
                if product.product_id in missing_products_ids
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
