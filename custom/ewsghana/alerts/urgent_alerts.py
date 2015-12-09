from collections import defaultdict
from datetime import datetime, timedelta
from corehq.apps.commtrack.models import StockState
from corehq.apps.locations.dbaccessors import get_web_users_by_location
from corehq.apps.locations.models import SQLLocation
from corehq.apps.reminders.util import get_preferred_phone_number_for_recipient
from custom.ewsghana.alerts import URGENT_STOCKOUT, URGENT_NON_REPORTING
from custom.ewsghana.alerts.alert import Notification


class UrgentAlert(object):

    message = None

    def __init__(self, domain):
        self.domain = domain

    def get_sql_products_list(self, sql_location):
        raise NotImplemented()

    def get_sql_locations(self):
        return SQLLocation.active_objects.filter(domain=self.domain, location_type__administrative=True)

    def get_users(self, sql_location):
        return [
            user
            for user in get_web_users_by_location(self.domain, sql_location.location_id)
            if get_preferred_phone_number_for_recipient(user)
        ]

    def send(self):
        raise NotImplemented()


class UrgentStockoutAlert(UrgentAlert):

    def get_sql_products_list(self, sql_location):
        children = sql_location.get_descendants().filter(location_type__administrative=False)
        product_result_map = defaultdict(lambda: {'stockouts': 0, 'total': 0})
        for child in children:
            products = set(child.products)
            for product in products:
                product_result_map[product]['total'] += 1
            stockouts = StockState.objects.filter(
                sql_location=child,
                stock_on_hand=0,
                sql_product__in=products
            ).exclude(sql_product__is_archived=True)
            for stockout in stockouts:
                product_result_map[stockout.sql_product]['stockouts'] += 1

        return [
            sql_product
            for sql_product, result in product_result_map.iteritems()
            if result['total'] != 0 and result['stockouts'] / float(result['total']) > 0.5
        ]

    def get_message(self, location_name, user, sql_products=None):
        program_id = user.get_domain_membership(self.domain).program_id

        if program_id:
            sql_products = filter(lambda p: p.program_id == program_id, sql_products)

        if not sql_products:
            return

        return URGENT_STOCKOUT % (location_name, ', '.join(
            sorted([sql_product.name for sql_product in sql_products])
        ))

    def get_notifications(self):
        for sql_location in self.get_sql_locations():
            products = self.get_sql_products_list(sql_location)
            for user in self.get_users(sql_location):
                message = self.get_message(sql_location.name, user, products)
                if message:
                    yield Notification(self.domain, user, message)

    def send(self):
        for notification in self.get_notifications():
            notification.send()


class UrgentNonReporting(UrgentAlert):

    def get_message(self, sql_location):
        thirty_days_ago = datetime.utcnow() - timedelta(days=30)
        children = sql_location.get_descendants().filter(location_type__administrative=False)
        total = children.count()
        reported = StockState.objects.filter(
            sql_location__in=children,
            last_modified_date__gte=thirty_days_ago
        ).exclude(sql_product__is_archived=True).values_list('case_id', flat=True).distinct().count()

        if total != 0 and reported / total < 0.5:
            return URGENT_NON_REPORTING % sql_location.name

    def get_notifications(self):
        for sql_location in self.get_sql_locations():
            message = self.get_message(sql_location)
            if not message:
                continue
            for user in self.get_users(sql_location):
                yield Notification(self.domain, user, message)

    def send(self):
        for notification in self.get_notifications():
            notification.send()
