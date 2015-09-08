import json
import os
from custom.ilsgateway.api import ILSGatewayEndpoint


class MockEndpoint(ILSGatewayEndpoint):
    datapath = os.path.join(os.path.dirname(__file__), 'data')

    def get_groups(self, **kwargs):
        return {}, []

    def get_objects(self, url, params=None, filters=None, limit=1000, offset=0, **kwargs):
        if 'locations' in url:
            return self._from_json('sample_locations.json', **kwargs)
        elif 'smsusers' in url:
            return self._from_json('sample_smsusers.json', **kwargs)
        elif 'webusers' in url:
            return self._from_json('sample_webusers.json', **kwargs)
        elif 'product' in url:
            return self._from_json('sample_products.json', **kwargs)
        elif 'stocktransactions' in url:
            meta, objects = self._from_json('sample_stocktransactions.json', **kwargs)
            if filters.get('supply_point'):
                objects = filter(lambda x: str(x['supply_point']) == filters['supply_point'], objects)
            return meta, objects
        elif 'supplypointstatus' in url:
            meta, objects = self._from_json('sample_supplypointstatuses.json', **kwargs)
            if filters.get('supply_point'):
                objects = filter(lambda x: str(x['supply_point']) == filters['supply_point'], objects)
            return meta, objects
        elif 'deliverygroupreports' in url:
            meta, objects = self._from_json('sample_deliverygroupreports.json', **kwargs)
            if filters.get('supply_point'):
                objects = filter(lambda x: str(x['supply_point']) == filters['supply_point'], objects)
            return meta, objects

    def _from_json(self, filename, **kwargs):
        with open(os.path.join(self.datapath, filename)) as f:
            objects = json.loads(f.read())
            meta = {
                "limit": 100,
                "next": None,
                "offset": 0,
                "previous": None,
                "total_count": len(objects)
            }
            return meta, objects

    def get_location(self, id, params=None):
        with open(os.path.join(self.datapath, 'sample_locations.json')) as f:
            objects = [location for location in json.loads(f.read())]
            if id == 2632:
                return objects[0]
            elif id == 1:
                return objects[1]
            elif id == 2625:
                return objects[2]
            elif id == 13:
                return objects[3]
            elif id == 25:
                return objects[4]
            elif id == 50:
                return objects[5]
            elif id == 51:
                return objects[6]
