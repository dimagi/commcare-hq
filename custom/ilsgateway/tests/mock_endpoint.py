import json
import os
from custom.ilsgateway.api import ILSGatewayEndpoint, Location


class MockEndpoint(ILSGatewayEndpoint):
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
            if id == 2632:
                return objects[0]
            elif id == 1:
                return objects[1]
            elif id == 2625:
                return objects[2]
            elif id == 13:
                return objects[3]
