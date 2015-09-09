import logging
from corehq import Domain
from corehq.apps.custom_data_fields import CustomDataFieldsDefinition
from corehq.apps.custom_data_fields.models import CustomDataField
from corehq.apps.locations.models import SQLLocation

from corehq.apps.products.models import Product
from custom.ilsgateway.models import ILSGatewayConfig
from dimagi.utils.dates import force_to_datetime
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.conf import settings
import requests
from corehq.apps.sms.mixin import PhoneNumberInUseException, VerifiedNumber, apply_leniency, InvalidFormatException, \
    MobileBackend
from corehq.apps.users.models import CouchUser, CommCareUser, WebUser
from custom.api.utils import EndpointMixin, apply_updates
from dimagi.utils.decorators.memoized import memoized


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
        raise NotImplemented()


class ApiSyncObject(object):
    name = None
    get_objects_function = None
    sync_function = None
    filters = {}

    def __init__(self, name, get_objects_function, sync_function, date_filter_name=None, filters=None,
                 migrate_once=False, is_date_range=False):
        self.name = name
        self.get_objects_function = get_objects_function
        self.sync_function = sync_function
        self.date_filter_name = date_filter_name
        self.filters = filters or {}
        self.migrate_once = migrate_once
        self._is_date_range = is_date_range

    def add_date_filter(self, start_date, end_date=None):
        if self.date_filter_name:
            self.filters[self.date_filter_name + '__gte'] = start_date

        if self._is_date_range and end_date:
            self.filters[self.date_filter_name + '__lte'] = end_date


class APISynchronization(object):

    LOCATION_CUSTOM_FIELDS = []
    SMS_USER_CUSTOM_FIELDS = []
    PRODUCT_CUSTOM_FIELDS = []

    def __init__(self, domain, endpoint):
        self.domain = domain
        self.endpoint = endpoint

    @property
    def apis(self):
        return []

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
                label = custom_field.get('label')
                choices = custom_field.get('choices') or []
                existing_fields = filter(lambda field: field.slug == name, fields_definitions.fields)
                if not existing_fields:
                    need_save = True
                    fields_definitions.fields.append(
                        CustomDataField(
                            slug=name,
                            label=label or name,
                            is_required=False,
                            choices=choices,
                            is_multiple_choice=custom_field.get('is_multiple_choice', False)
                        )
                    )
                else:
                    existing_field = existing_fields[0]
                    if set(existing_field.choices) != set(choices):
                        existing_field.choices = choices
                        need_save = True

            if need_save:
                fields_definitions.save()

    @memoized
    def _get_logistics_domains(self):
        from custom.ewsghana.models import EWSGhanaConfig
        return ILSGatewayConfig.get_all_enabled_domains() + EWSGhanaConfig.get_all_enabled_domains()

    def set_default_backend(self):
        domain_object = Domain.get_by_name(self.domain)
        domain_object.default_sms_backend_id = MobileBackend.load_by_name(None, 'MOBILE_BACKEND_TEST').get_id
        domain_object.save()

    def create_or_edit_roles(self):
        raise NotImplemented("Not implemented yet")

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
            # I don't know why sample_webusers.json has these in a number o
            # different formats, w/ and w/o 'T', with timezone offset, etc
            # I do not know how timezones are meant to be handled, so I am
            # conservatively keeping the behavior the same by explicitly
            # stripping the timezone with no conversion
            # todo: this is almost certainly not what was intended
            'last_login': force_to_datetime(ilsgateway_webuser.last_login).replace(tzinfo=None),
            'date_joined': force_to_datetime(ilsgateway_webuser.date_joined).replace(tzinfo=None),
            'password_hashed': True,
        }
        location_id = None
        if ilsgateway_webuser.location:
            try:
                sql_location = SQLLocation.objects.get(domain=self.domain, external_id=ilsgateway_webuser.location)
                location_id = sql_location.location_id
            except SQLLocation.DoesNotExist:
                location_id = None

        if user is None:
            try:
                user = WebUser.create(domain=None, username=username,
                                      password=ilsgateway_webuser.password, email=ilsgateway_webuser.email.lower(),
                                      **user_dict)
                user.add_domain_membership(self.domain, location_id=location_id)
                user.save()
            except Exception as e:
                if settings.UNIT_TESTING:
                    raise
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
            cleaned_number = apply_leniency(ilsgateway_smsuser.phone_numbers[0])
            if cleaned_number:
                user_dict['phone_numbers'] = [cleaned_number]
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
                        user.save_verified_number(self.domain, user_dict["phone_numbers"][0], True)
                    except PhoneNumberInUseException as e:
                        self._reassign_number(user, user_dict["phone_numbers"][0])
                    except InvalidFormatException:
                        pass
            except Exception as e:
                logging.error(e)
        else:
            verified_number = user.get_verified_number()
            phone_number = verified_number.phone_number if verified_number else None
            if apply_updates(user, user_dict):
                if user_dict.get('phone_numbers'):
                    new_phone_number = user_dict['phone_numbers'][0]
                    if new_phone_number != phone_number:
                        if phone_number:
                            user.delete_verified_number(phone_number)
                        self._save_verified_number(user, new_phone_number)
                elif phone_number:
                    user.phone_numbers = []
                    user.delete_verified_number(phone_number)
                user.save()
        return user

    def _save_verified_number(self, user, phone_number):
        try:
            user.save_verified_number(self.domain, phone_number, True)
        except PhoneNumberInUseException:
            self._reassign_number(user, phone_number)
        except InvalidFormatException:
            pass

    def _reassign_number(self, user, phone_number):
        v = VerifiedNumber.by_phone(phone_number, include_pending=True)
        if v.domain in self._get_logistics_domains():
            v.delete()
            user.save_verified_number(self.domain, phone_number, True)

    def add_language_to_user(self, logistics_sms_user):
        domain_part = "%s.commcarehq.org" % self.domain
        username_part = "%s%d" % (logistics_sms_user.name.strip().replace(' ', '.').lower(),
                                  logistics_sms_user.id)
        username = "%s@%s" % (username_part[:(128 - (len(domain_part) + 1))], domain_part)
        user = CouchUser.get_by_username(username)
        if not user:
            return

        if user.language != logistics_sms_user.language:
            user.language = logistics_sms_user.language
            user.save()

        logistics_numbers = {apply_leniency(phone_number) for phone_number in logistics_sms_user.phone_numbers}
        if set(user.phone_numbers) == logistics_numbers:
            return

        for phone_number in user.phone_numbers:
            user.delete_phone_number(phone_number)

        if logistics_sms_user.phone_numbers:
            phone_number = apply_leniency(logistics_sms_user.phone_numbers[0])
            if not phone_number:
                return
            user.set_default_phone_number(phone_number)
            self._save_verified_number(user, phone_number)
