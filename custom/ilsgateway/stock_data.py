from django.db.models import Q
from corehq.apps.locations.models import SQLLocation
from custom.ilsgateway.models import ILSGatewayConfig
from custom.ilsgateway.tanzania.warehouse.const import TEST_REGION_ID
from custom.ilsgateway.tasks import sync_supply_point_status, sync_delivery_group_report, \
    process_supply_point_status, process_delivery_group_report
from custom.logistics.api import ApiSyncObject
from custom.logistics.stock_data import StockDataSynchronization
from custom.logistics.tasks import sync_stock_transactions_for_facility, sync_stock_transaction


class ILSStockDataSynchronization(StockDataSynchronization):

    @property
    def apis(self):
        return (
            ('stock_transaction', sync_stock_transactions_for_facility),
            ('supply_point_status', sync_supply_point_status),
            ('delivery_group', sync_delivery_group_report)
        )

    @property
    def all_stock_data(self):
        return ILSGatewayConfig.for_domain(self.domain).all_stock_data

    def get_location_id(self, facility):
        return SQLLocation.objects.get(domain=self.domain, external_id=facility).location_id

    def get_ids(self):
        return SQLLocation.objects.filter(
            domain=self.domain
        ).exclude(external_id__isnull=True).order_by('created_at').values_list('external_id', flat=True)

    @property
    def test_facilities(self):
        test_region = SQLLocation.objects.get(domain=self.domain, external_id=TEST_REGION_ID)
        return SQLLocation.objects.filter(
            Q(domain=self.domain) & (Q(parent=test_region) | Q(parent__parent=test_region))
        ).order_by('id').values_list('external_id', flat=True)

    def get_last_processed_location(self, checkpoint):
        return checkpoint.location.external_id

    def get_stock_apis_objects(self):
        return [
            ApiSyncObject(
                'stock_transaction',
                get_objects_function=self.endpoint.get_stocktransactions,
                sync_function=sync_stock_transaction,
                date_filter_name='date',
                is_date_range=True
            ),
            ApiSyncObject(
                'supply_point_status',
                get_objects_function=self.endpoint.get_supplypointstatuses,
                sync_function=process_supply_point_status,
                date_filter_name='status_date',
                is_date_range=True
            ),
            ApiSyncObject(
                'delivery_group',
                get_objects_function=self.endpoint.get_deliverygroupreports,
                sync_function=process_delivery_group_report,
                date_filter_name='report_date',
                is_date_range=True
            )
        ]
