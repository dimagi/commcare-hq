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


class ILSUser(object):

    def __init__(self, username, first_name, last_name, email, password, is_staff, is_active, is_superuser, last_login,
                 date_joined, location, supply_point):
        self.username = username
        self.first_name = first_name
        self.last_name = last_name
        self.email = email
        self.password = password
        self.is_staff = is_staff
        self.is_active = is_active
        self.is_superuser = is_superuser
        self.last_login = last_login
        self.date_joined = date_joined
        self.location = location
        self.supply_point = supply_point

    @classmethod
    def from_json(cls, json_rep):
        return cls(
            username=json_rep['username'],
            first_name=json_rep['first_name'],
            last_name=json_rep['last_name'],
            email=json_rep['email'],
            password=json_rep['password'],
            is_staff=json_rep['is_staff'],
            is_active=json_rep['is_active'],
            is_superuser=json_rep['is_superuser'],
            last_login=json_rep['last_login'],
            date_joined=json_rep['date_joined'],
            location=json_rep['location'],
            supply_point=json_rep['supply_point']
        )


class ILSGatewayEndpoint(EndpointMixin):

    def __init__(self, base_uri, username, password):
        self.base_uri = base_uri.rstrip('/')
        self.username = username
        self.password = password
        self.products_url = self._urlcombine(self.base_uri, '/products/')
        self.webusers_url = self._urlcombine(self.base_uri, '/webusers')

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

    def get_webusers(self):
        users = self.get_objects(self.webusers_url)
        for user in users:
            yield ILSUser.from_json(user)
