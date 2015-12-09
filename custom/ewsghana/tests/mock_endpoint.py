import json
import os
from custom.ewsghana.api import GhanaEndpoint, SMSUser


class MockEndpoint(GhanaEndpoint):
    datapath = os.path.join(os.path.dirname(__file__), 'data')

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

    def _from_json(self, filename, **kwargs):
        with open(os.path.join(self.datapath, filename)) as f:
            objects = json.loads(f.read())
            meta = {
                "limit": 1000,
                "next": None,
                "offset": 0,
                "previous": None,
                "total_count": len(objects)
            }
            return meta, objects

    def get_location(self, id, params=None):
        with open(os.path.join(self.datapath, 'sample_locations.json')) as f:
            objects = [location for location in json.loads(f.read())]
        if id == 1:
            return objects[0]
        elif id == 620:
            return objects[1]
        elif id == 369:
            return objects[2]
        elif id == 319:
            return objects[3]
        elif id == 621:
            return objects[4]
        elif id == 15:
            return objects[5]
        elif id == 1000:
            return objects[6]
        elif id == 899:
            return objects[7]
        elif id == 900:
            return objects[8]

    def get_smsuser(self, user_id, **kwargs):
        with open(os.path.join(self.datapath, 'sample_locations.json')) as f:
            objects = json.loads(f.read())
            if user_id == 2342:
                return SMSUser(objects[0])
