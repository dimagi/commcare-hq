from custom.ilsgateway.models import SupplyPointStatusTypes
from custom.ilsgateway.tanzania.reminders import REMINDER_STOCKONHAND
from casexml.apps.stock.models import StockTransaction
from custom.ilsgateway.tanzania.reminders.reminder import Reminder


class SOHReminder(Reminder):

    def get_message(self):
        return REMINDER_STOCKONHAND

    def get_status_type(self):
        return SupplyPointStatusTypes.SOH_FACILITY

    def location_filter(self, sql_location):
        return not StockTransaction.objects.filter(
            case_id=sql_location.supply_point_id,
            report__date__gte=self.date,
            type='stockonhand'
        ).exists()
