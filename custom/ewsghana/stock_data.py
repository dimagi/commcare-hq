from corehq.apps.commtrack.dbaccessors import \
    get_supply_point_case_by_location_id
from corehq.apps.commtrack.models import SupplyPointCase
from corehq.apps.hqcase.dbaccessors import \
    get_supply_point_case_in_domain_by_id
from corehq.apps.locations.models import SQLLocation
from custom.ewsghana.models import EWSGhanaConfig
from custom.logistics.api import ApiSyncObject
from custom.logistics.stock_data import StockDataSynchronization
from custom.logistics.tasks import sync_stock_transactions_for_facility, sync_stock_transaction
from dimagi.utils.couch.database import iter_docs


class EWSStockDataSynchronization(StockDataSynchronization):

    @property
    def apis(self):
        return (
            ('stock_transaction', sync_stock_transactions_for_facility),
        )

    @property
    def all_stock_data(self):
        return EWSGhanaConfig.for_domain(self.domain).all_stock_data

    def get_location_id(self, facility):
        sp = get_supply_point_case_in_domain_by_id(self.domain, facility)
        return sp.location_id

    def get_ids(self):
        supply_points_ids = SQLLocation.objects.filter(
            domain=self.domain,
            location_type__administrative=False
        ).order_by('created_at').values_list('supply_point_id', flat=True)
        return [
            doc['external_id']
            for doc in iter_docs(SupplyPointCase.get_db(), supply_points_ids)
            if doc['external_id']
        ]

    @property
    def test_facilities(self):
        return [
            304, 324, 330, 643, 327, 256, 637, 332, 326, 338, 340, 331, 347, 27, 975, 346, 477, 344, 339,
            458, 748, 18, 379, 456, 644, 462, 459, 475, 638, 969, 480, 464, 960, 529, 255, 16, 31, 639, 640,
            11, 15, 25, 645, 95, 13, 970, 952, 470, 971, 474, 962, 479, 953, 457, 476, 481, 501, 500, 499,
            503, 502, 498, 496, 497, 10, 333, 963, 335, 972, 914, 527, 26, 531, 469, 530, 523, 19, 915, 524,
            528, 325, 20, 460, 468, 916, 646, 519, 345, 471, 633, 518, 642, 328, 343, 21, 467, 648, 334, 473,
            6, 342, 28, 478, 472, 955, 964, 636, 258, 918, 466, 337, 956, 809, 965, 24, 974, 957, 954, 22,
            29, 958, 967, 917, 951, 515, 8, 959, 968, 649, 966, 341, 336, 647, 973, 5, 517, 522, 465, 635,
            526, 4, 30, 1, 14, 23, 521, 532, 516, 461, 520, 525, 961, 641, 257, 348
        ]

    def get_last_processed_location(self, checkpoint):
        supply_point = get_supply_point_case_by_location_id(
            self.domain, checkpoint.location.location_id)
        external_id = supply_point.external_id if supply_point else None
        return external_id

    def get_stock_apis_objects(self):
        return [
            ApiSyncObject(
                'stock_transaction',
                get_objects_function=self.endpoint.get_stocktransactions,
                sync_function=sync_stock_transaction,
                date_filter_name='date',
                is_date_range=True
            )
        ]
