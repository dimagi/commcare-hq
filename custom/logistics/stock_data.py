from celery import chain
from custom.logistics.api import ApiSyncObject


class StockDataSynchronization(object):

    def __init__(self, domain, endpoint):
        self.domain = domain
        self.endpoint = endpoint

    @property
    def apis(self):
        raise NotImplemented()

    @property
    def test_facilities(self):
        return []

    def get_location_id(self, facility):
        raise NotImplemented()

    def get_ids(self):
        raise NotImplemented()

    def all_stock_data(self):
        raise NotImplemented()

    def get_last_processed_location(self, checkpoint):
        raise NotImplemented()

    def get_stock_apis_objects(self):
        raise NotImplemented()

    def process_data(self, task, chunk):
        res = chain(task.si(self, fac) for fac in chunk)()
        res.get()


class StockDataApiSync(ApiSyncObject):

    def add_supply_point_param(self, supply_point_id):
        self.filters['supply_point'] = supply_point_id
