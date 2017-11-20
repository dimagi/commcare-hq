from __future__ import absolute_import
from casexml.apps.stock.models import StockTransaction
from custom.ilsgateway.tanzania.reminders import SOH_THANK_YOU
from custom.ilsgateway.tanzania.reminders.reminder import Reminder


class SOHThankYouReminder(Reminder):

    def get_message(self):
        return SOH_THANK_YOU

    def get_status_type(self):
        return None

    def location_filter(self, sql_location):
        return StockTransaction.objects.filter(
            case_id=sql_location.supply_point_id,
            report__date__gte=self.date,
            type__in=['stockonhand', 'stockout']
        ).exists()
