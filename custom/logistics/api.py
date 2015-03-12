import logging
from corehq.apps.custom_data_fields import CustomDataFieldsDefinition
from corehq.apps.custom_data_fields.models import CustomDataField

from corehq.apps.products.models import Product
from dimagi.utils.dates import force_to_datetime
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
import requests
from corehq.apps.commtrack.models import SupplyPointCase
from corehq.apps.sms.mixin import PhoneNumberInUseException, VerifiedNumber
from corehq.apps.users.models import CouchUser, CommCareUser, WebUser
from custom.api.utils import EndpointMixin, apply_updates


class MigrationException(Exception):
    pass


class LogisticsEndpoint(EndpointMixin):
    models_map = {}

    def __init__(self, base_uri, username, password):
        self.base_uri = base_uri.rstrip('/')
        self.username = username
        self.password = password
        self.products_url = self._urlcombine(self.base_uri, '/products/')
        self.webusers_url = self._urlcombine(self.base_uri, '/webusers/')
        self.smsusers_url = self._urlcombine(self.base_uri, '/smsusers/')
        self.locations_url = self._urlcombine(self.base_uri, '/locations/')
        self.productstock_url = self._urlcombine(self.base_uri, '/productstocks/')
        self.stocktransactions_url = self._urlcombine(self.base_uri, '/stocktransactions/')

    def get_objects(self, url, params=None, filters=None, limit=100, offset=0, **kwargs):
        params = params if params else {}
        if filters:
            params.update(filters)

        params.update({
            'limit': limit,
            'offset': offset
        })

        if 'next_url_params' in kwargs and kwargs['next_url_params']:
            url = url + "?" + kwargs['next_url_params']
            params = {}

        response = requests.get(url, params=params,
                                auth=self._auth())
        if response.status_code == 200 and 'objects' in response.json():
            meta = response.json()['meta']
            objects = response.json()['objects']
        elif response.status_code == 401:
            raise MigrationException('Invalid credentials.')
        else:
            raise MigrationException('Something went wrong during migration.')

        return meta, objects

    def get_products(self, **kwargs):
        meta, products = self.get_objects(self.products_url, **kwargs)
        return meta, [(self.models_map['product'])(product) for product in products]

    def get_webusers(self, **kwargs):
        meta, users = self.get_objects(self.webusers_url, **kwargs)
        return meta, [(self.models_map['webuser'])(user) for user in users]

    def get_smsusers(self, **kwargs):
        meta, users = self.get_objects(self.smsusers_url, **kwargs)
        return meta, [(self.models_map['smsuser'])(user) for user in users]

    def get_location(self, id, params=None):
        response = requests.get(self.locations_url + str(id) + "/", params=params, auth=self._auth())
        return response.json()

    def get_locations(self, **kwargs):
        meta, locations = self.get_objects(self.locations_url, **kwargs)
        return meta, [(self.models_map['location'])(location) for location in locations]

    def get_productstocks(self, **kwargs):
        meta, product_stocks = self.get_objects(self.productstock_url, **kwargs)
        return meta, [(self.models_map['product_stock'])(product_stock) for product_stock in product_stocks]

    def get_stocktransactions(self, **kwargs):
        meta, stock_transactions = self.get_objects(self.stocktransactions_url, **kwargs)
        return meta, [(self.models_map['stock_transaction'])(stock_transaction)
                      for stock_transaction in stock_transactions]


class APISynchronization(object):

    LOCATION_CUSTOM_FIELDS = []
    SMS_USER_CUSTOM_FIELDS = []
    PRODUCT_CUSTOM_FIELDS = []

    def __init__(self, domain, endpoint):
        self.domain = domain
        self.endpoint = endpoint

    def prepare_commtrack_config(self):
        """
        Bootstraps the domain-level metadata according to the static config.
        """
        raise NotImplemented("Not implemented yet")

    def prepare_custom_fields(self):
        """
        Sets the proper custom user data/location/product fields on the domain.
        """
        self.save_custom_fields('LocationFields', self.LOCATION_CUSTOM_FIELDS)
        self.save_custom_fields('UserFields', self.SMS_USER_CUSTOM_FIELDS)
        self.save_custom_fields('ProductFields', self.PRODUCT_CUSTOM_FIELDS)

    def save_custom_fields(self, definition_name, custom_fields):
        if custom_fields:
            fields_definitions = CustomDataFieldsDefinition.get_or_create(self.domain, definition_name)
            need_save = False
            for custom_field in custom_fields:
                name = custom_field.get('name')
                choices = custom_field.get('choices') or []
                existing_fields = filter(lambda field: field.slug == name, fields_definitions.fields)
                if not existing_fields:
                    need_save = True
                    fields_definitions.fields.append(
                        CustomDataField(
                            slug=name,
                            label=name,
                            is_required=False,
                        )
                    )
                else:
                    existing_field = existing_fields[0]
                    if set(existing_field.choices) != set(choices):
                        existing_field.choices = choices
                        need_save = True

            if need_save:
                fields_definitions.save()

    def location_sync(self, ilsgateway_location):
        raise NotImplemented("Not implemented yet")

    def product_sync(self, ilsgateway_product):
        product = Product.get_by_code(self.domain, ilsgateway_product.sms_code)
        product_dict = {
            'domain': self.domain,
            'name': ilsgateway_product.name,
            'code': ilsgateway_product.sms_code,
            'unit': str(ilsgateway_product.units),
            'description': ilsgateway_product.description,
        }
        if product is None:
            product = Product(**product_dict)
            product.save()
        else:
            if apply_updates(product, product_dict):
                product.save()
        return product

    def web_user_sync(self, ilsgateway_webuser):
        username = ilsgateway_webuser.email.lower()
        if not username:
            try:
                validate_email(ilsgateway_webuser.username)
                username = ilsgateway_webuser.username
            except ValidationError:
                return None
        user = WebUser.get_by_username(username)
        user_dict = {
            'first_name': ilsgateway_webuser.first_name,
            'last_name': ilsgateway_webuser.last_name,
            'is_active': ilsgateway_webuser.is_active,
            'last_login': force_to_datetime(ilsgateway_webuser.last_login),
            'date_joined': force_to_datetime(ilsgateway_webuser.date_joined),
            'password_hashed': True,
        }
        sp = SupplyPointCase.view('hqcase/by_domain_external_id',
                                  key=[self.domain, str(ilsgateway_webuser.location)],
                                  reduce=False,
                                  include_docs=True,
                                  limit=1).first()
        location_id = sp.location_id if sp else None

        if user is None:
            try:
                user = WebUser.create(domain=None, username=username,
                                      password=ilsgateway_webuser.password, email=ilsgateway_webuser.email,
                                      **user_dict)
                user.add_domain_membership(self.domain, location_id=location_id)
                user.save()
            except Exception as e:
                logging.error(e)
        else:
            if self.domain not in user.get_domains():
                user.add_domain_membership(self.domain, location_id=location_id)
                user.save()
        return user

    def sms_user_sync(self, ilsgateway_smsuser, username_part=None, password=None,
                      first_name='', last_name=''):
        domain_part = "%s.commcarehq.org" % self.domain
        if not username_part:
            username_part = "%s%d" % (ilsgateway_smsuser.name.strip().replace(' ', '.').lower(),
                                      ilsgateway_smsuser.id)
        username = "%s@%s" % (username_part[:(128 - (len(domain_part) + 1))], domain_part)
        # sanity check
        assert len(username) <= 128
        user = CouchUser.get_by_username(username)
        splitted_value = ilsgateway_smsuser.name.split(' ', 1)
        if not first_name:
            first_name = splitted_value[0][:30] if splitted_value else ''

        if not last_name:
            last_name = splitted_value[1][:30] if len(splitted_value) > 1 else ''

        language = ilsgateway_smsuser.language

        user_dict = {
            'first_name': first_name,
            'last_name': last_name,
            'is_active': bool(ilsgateway_smsuser.is_active),
            'email': ilsgateway_smsuser.email,
            'user_data': {}
        }

        if ilsgateway_smsuser.role:
            user_dict['user_data']['role'] = ilsgateway_smsuser.role

        if ilsgateway_smsuser.phone_numbers:
            user_dict['phone_numbers'] = [ilsgateway_smsuser.phone_numbers[0].replace('+', '')]
            user_dict['user_data']['backend'] = ilsgateway_smsuser.backend

        if user is None and username_part:
            try:
                user_password = password or User.objects.make_random_password()
                user = CommCareUser.create(domain=self.domain, username=username, password=user_password,
                                           email=ilsgateway_smsuser.email, commit=False,
                                           password_hashed=bool(password))
                user.first_name = first_name
                user.last_name = last_name
                user.language = language
                user.is_active = bool(ilsgateway_smsuser.is_active)
                user.user_data = user_dict["user_data"]
                if "phone_numbers" in user_dict:
                    user.set_default_phone_number(user_dict["phone_numbers"][0])
                    try:
                        user.save_verified_number(self.domain, user_dict["phone_numbers"][0], True,
                                                  ilsgateway_smsuser.backend)
                    except PhoneNumberInUseException as e:
                        v = VerifiedNumber.by_phone(user_dict["phone_numbers"][0], include_pending=True)
                        v.delete()
                        user.save_verified_number(self.domain, user_dict["phone_numbers"][0], True,
                                                  ilsgateway_smsuser.backend)
            except Exception as e:
                logging.error(e)
        else:
            if apply_updates(user, user_dict):
                user.save()
        return user

    def add_language_to_user(self, logistics_sms_user, domains=None):
        if not domains:
            domains = []
        domain_part = "%s.commcarehq.org" % self.domain
        username_part = "%s%d" % (logistics_sms_user.name.strip().replace(' ', '.').lower(),
                                  logistics_sms_user.id)
        username = "%s@%s" % (username_part[:(128 - (len(domain_part) + 1))], domain_part)
        user = CouchUser.get_by_username(username)
        if user and user.language != logistics_sms_user.language:
            user.language = logistics_sms_user.language
            user.save()

        for phone_number in user.phone_numbers:
            user.delete_phone_number(phone_number)

        if logistics_sms_user.phone_numbers:
            phone_number = logistics_sms_user.phone_numbers[0]
            user.set_default_phone_number(phone_number)
            try:
                user.save_verified_number(self.domain, phone_number, True,
                                          logistics_sms_user.backend)
            except PhoneNumberInUseException:
                v = VerifiedNumber.by_phone(phone_number, include_pending=True)
                if v.domain in domains:
                    v.delete()
                    user.save_verified_number(self.domain, phone_number, True,
                                              logistics_sms_user.backend)
