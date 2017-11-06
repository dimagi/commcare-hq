from __future__ import absolute_import
from casexml.apps.stock.models import StockTransaction
from corehq.apps.locations.models import SQLLocation
from custom.ilsgateway.models import SLABConfig
from custom.ilsgateway.slab.messages import REMINDER_STOCKOUT
from custom.ilsgateway.slab.utils import stockedout_products, overstocked_products
from custom.ilsgateway.tanzania.reminders.reminder import Reminder
from custom.ilsgateway.utils import send_translated_message


class StockoutReminder(Reminder):

    def location_filter(self, sql_location):
        return True

    def get_sql_locations(self):
        case_ids = SLABConfig.objects.filter(is_pilot=True).values_list(
            'sql_location__supply_point_id', flat=True
        )
        case_ids = list(StockTransaction.objects.filter(
            case_id__in=case_ids, report__date__gte=self.date, type__in=['stockonhand', 'stockout']
        ).values_list('case_id', flat=True))
        return SQLLocation.objects.filter(supply_point_id__in=case_ids)

    def send(self):
        for sql_location in self.get_sql_locations():
            stockedout_products_set = set(stockedout_products(sql_location))
            slab_config = SLABConfig.objects.get(sql_location=sql_location)
            overstocked_str = ""
            for closest_sql_location in slab_config.closest_supply_points.all():
                overstocked_products_set = set(
                    [overstock[0] for overstock in overstocked_products(closest_sql_location)]
                )
                intersection = stockedout_products_set.intersection(overstocked_products_set)
                if intersection:
                    overstocked_str += "%s (%s)" % (closest_sql_location.name, ', '.join(sorted(intersection)))

            if not overstocked_str:
                continue

            for user in self.get_location_users(sql_location):
                send_translated_message(user, REMINDER_STOCKOUT % {
                    'products_list': ', '.join(sorted(stockedout_products_set)),
                    'overstocked_list': overstocked_str
                })
