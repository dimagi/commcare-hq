import logging
import requests
from custom.api.utils import EndpointMixin


class Product(object):

    def __init__(self, name, units, sms_code, description, is_active):
        self.name = name
        self.units = units
        self.sms_code = sms_code
        self.description = description
        self.is_active = is_active

    @classmethod
    def from_json(cls, json_rep):
        return cls(
            name=json_rep['name'],
            units=json_rep['units'],
            sms_code=json_rep['sms_code'],
            description=json_rep['description'],
            is_active=json_rep['is_active']
        )


class ILSGatewayEndpoint(EndpointMixin):

    def __init__(self, base_uri, username, password):
        self.base_uri = base_uri.rstrip('/')
        self.username = username
        self.password = password
        self.products_url = self._urlcombine(self.base_uri, '/products/')

    def get_objects(self, url, params=None):
        params = {} if params else params
        response = requests.get(url, params=params,
                                auth=self._auth())
        objects = []
        if response.status_code == 200 and 'objects' in response.json():
            objects = response.json()['objects']
        return objects

    def get_products(self):
        products = self.get_objects(self.products_url)
        for product in products:
            yield Product.from_json(product)
