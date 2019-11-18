from datetime import datetime, timedelta
from django.db.models.aggregates import Max
from casexml.apps.stock.models import StockTransaction
from corehq.apps.locations.models import SQLLocation
from corehq.apps.products.models import SQLProduct
from custom.ewsghana.alerts import ONGOING_STOCKOUT_AT_SDP, ONGOING_STOCKOUT_AT_RMS
from custom.ewsghana.alerts.alert import WeeklyAlert


class OnGoingStockouts(WeeklyAlert):

    message = ONGOING_STOCKOUT_AT_SDP
    filters = {}

    def get_sql_locations(self):
        return SQLLocation.active_objects.filter(
            domain=self.domain, location_type__name__in=['region', 'district']
        )

    def program_clause(self, user_program, reported_programs):
        return not user_program or user_program in reported_programs

    def get_descendants(self, sql_location):
        return sql_location.get_descendants().filter(location_type__administrative=False)\
            .exclude(location_type__name='Regional Medical Store').exclude(is_archived=True)

    def get_data(self, sql_location):
        data = {}
        date_until = datetime.utcnow() - timedelta(days=21)
        for child in self.get_descendants(sql_location):
            location_products = set(child.products)
            transactions = StockTransaction.objects.filter(
                sql_product__in=location_products,
                report__date__gte=date_until,
                case_id=child.supply_point_id
            ).values(
                'product_id'
            ).annotate(max_soh=Max('stock_on_hand'))

            data[child.name] = {
                SQLProduct.objects.get(product_id=tx['product_id']).program_id
                for tx in transactions
                if tx['max_soh'] == 0
            }

            if not data[child.name]:
                del data[child.name]
        return data


class OnGoingStockoutsRMS(OnGoingStockouts):

    message = ONGOING_STOCKOUT_AT_RMS
    filters = {
        'location_type__name': 'Regional Medical Store'
    }

    def get_descendants(self, sql_location):
        return sql_location.get_descendants().filter(location_type__name='Regional Medical Store')

    def get_sql_locations(self):
        return SQLLocation.active_objects.filter(
            domain=self.domain, location_type__name__in=['country', 'region']
        )
