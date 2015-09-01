from datetime import datetime, timedelta
from django.db.models.aggregates import Count
from corehq.apps.commtrack.models import StockState
from corehq.apps.locations.dbaccessors import get_all_users_by_location
from corehq.apps.locations.models import SQLLocation
from corehq.apps.products.models import SQLProduct
from corehq.apps.sms.api import send_sms_to_verified_number
from custom.ewsghana.alerts import URGENT_STOCKOUT, URGENT_NON_REPORTING


class UrgentAlert(object):

    message = None

    def __init__(self, domain):
        self.domain = domain

    def get_sql_products_list(self, sql_location):
        raise NotImplemented()

    def get_sql_locations(self):
        return SQLLocation.objects.filter(domain=self.domain, location_type__administrative=True)

    def get_users(self, sql_location):
        return [
            user
            for user in get_all_users_by_location(self.domain, sql_location.location_id)
            if user.get_verified_number()
        ]

    def send(self):
        raise NotImplemented()


class UrgentStockoutAlert(UrgentAlert):

    def get_sql_products_list(self, sql_location):
        children = sql_location.get_descendants().filter(location_type__administrative=False)
        all_count = children.count()

        stockouts = StockState.objects.filter(
            sql_location__in=children,
            stock_on_hand=0
        ).values('product_id').annotate(facilities=Count('case_id'))

        return [
            SQLProduct.objects.get(product_id=stockout['product_id'])
            for stockout in stockouts
            if stockout['facilities'] / float(all_count) > 0.5
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

    def send(self):
        for sql_location in self.get_sql_locations():
            products = self.get_sql_products_list(sql_location)
            for user in self.get_users(sql_location):
                message = self.get_message(sql_location.name, user, products)
                if message:
                    send_sms_to_verified_number(user.get_verified_number(), message)


class UrgentNonReporting(UrgentAlert):

    def get_message(self, sql_location):
        thirty_days_ago = datetime.utcnow() - timedelta(days=30)
        children = sql_location.get_descendants().filter(location_type__administrative=False)
        total = children.count()
        reported = StockState.objects.filter(
            sql_location__in=children,
            last_modified_date__gte=thirty_days_ago
        ).values_list('case_id', flat=True).distinct().count()

        if reported / total < 0.5:
            return URGENT_NON_REPORTING % sql_location.name

    def send(self):
        for sql_location in self.get_sql_locations():
            for user in self.get_users(sql_location):
                message = self.get_message(sql_location)
                if message:
                    send_sms_to_verified_number(user.get_verified_number(), message)
