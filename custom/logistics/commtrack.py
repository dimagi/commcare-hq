import itertools
from functools import partial
import logging
import traceback

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from corehq.apps.locations.models import Location, SQLLocation
from corehq.apps.sms.mixin import PhoneNumberInUseException, VerifiedNumber
from corehq.apps.users.models import WebUser, CommCareUser, CouchUser, UserRole
from corehq.apps.domain.models import Domain
from custom.api.utils import apply_updates
from corehq.apps.commtrack.models import SupplyPointCase, CommtrackConfig, CommtrackActionConfig
from corehq.apps.locations.schema import LocationType
from corehq.apps.products.models import Product
from custom.logistics.models import MigrationCheckpoint
from dimagi.utils.dates import force_to_datetime
from custom.ilsgateway.models import HistoricalLocationGroup, ILSGatewayConfig
from requests.exceptions import ConnectionError
from datetime import datetime
from custom.ilsgateway.api import Location as Loc
from custom.ilsgateway.utils import get_next_meta_url


def retry(retry_max):
    def wrap(f):
        def wrapped_f(*args, **kwargs):
            retry_count = 0
            fail = False
            result = None
            while retry_count < retry_max:
                try:
                    result = f(*args, **kwargs)
                    fail = False
                    break
                except Exception:
                    retry_count += 1
                    fail = True
                    logging.error('%d/%d tries failed' % (retry_count, retry_max))
                    logging.error(traceback.format_exc())
            if fail:
                logging.error(f.__name__ + ": number of tries exceeds limit")
                logging.error("args: %s, kwargs: %s" % (args, kwargs))
            return result
        return wrapped_f
    return wrap


def smsusers_sync(project, endpoint, checkpoint, extension=None, **kwargs):
    has_next = True
    next_url = ""

    while has_next:
        meta, users = endpoint.get_smsusers(next_url_params=next_url, **kwargs)
        save_checkpoint(checkpoint, "smsuser",
                        meta.get('limit') or kwargs.get('limit'), meta.get('offset') or kwargs.get('offset'),
                        kwargs.get('date', None))
        for user in users:
            sms_user = sync_ilsgateway_smsuser(project, user)
            if extension:
                extension(sms_user, user)

        has_next, next_url = get_next_meta_url(has_next, meta, next_url)


def save_checkpoint(checkpoint, api, limit, offset, date, commit=True):
    checkpoint.limit = limit
    checkpoint.offset = offset
    checkpoint.api = api
    checkpoint.date = date
    if commit:
        checkpoint.save()


def products_sync(domain, endpoint, checkpoint, limit, offset, **kwargs):
    save_checkpoint(checkpoint, "product", limit, offset, kwargs.get('date', None))
    for product in endpoint.get_products(**kwargs):
        sync_ilsgateway_product(domain, product)


def webusers_sync(project, endpoint, checkpoint, limit, offset, **kwargs):
    has_next = True
    next_url = None

    while has_next:
        meta, webusers = endpoint.get_webusers(next_url_params=next_url, **kwargs)
        save_checkpoint(checkpoint, "webuser", meta.get('limit') or limit,
                        meta.get('offset') or offset, kwargs.get('date', None))
        for user in webusers:
            if user.email or user.username:
                sync_ilsgateway_webuser(project, user)
        has_next, next_url = get_next_meta_url(has_next, meta, next_url)


def locations_sync(project, endpoint, checkpoint, fetch_groups=True, **kwargs):
    has_next = True
    next_url = None

    while has_next:
        meta, locations = endpoint.get_locations(next_url_params=next_url, **kwargs)
        save_checkpoint(checkpoint, 'location_%s' % kwargs['filters']['type'],
                        meta.get('limit') or kwargs.get('limit'), meta.get('offset') or kwargs.get('offset'),
                        kwargs.get('date', None))
        for location in locations:
            sync_ilsgateway_location(project, endpoint, location, fetch_groups=fetch_groups)

        has_next, next_url = get_next_meta_url(has_next, meta, next_url)


@retry(5)
def sync_ilsgateway_product(domain, ilsgateway_product):
    product = Product.get_by_code(domain, ilsgateway_product.sms_code)
    product_dict = {
        'domain': domain,
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


@retry(5)
def sync_ilsgateway_webuser(domain, ilsgateway_webuser):
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
                              key=[domain, str(ilsgateway_webuser.location)],
                              reduce=False,
                              include_docs=True,
                              limit=1).first()
    role_id = UserRole.get_read_only_role_by_domain(domain).get_id
    location_id = sp.location_id if sp else None

    if user is None:
        try:
            user = WebUser.create(domain=None, username=username,
                                  password=ilsgateway_webuser.password, email=ilsgateway_webuser.email,
                                  **user_dict)
            user.add_domain_membership(domain, is_admin=False, role_id=role_id, location_id=location_id)
            user.save()
            check_hashes(user, user.get_django_user(), ilsgateway_webuser.password)
        except Exception as e:
            logging.error(e)
    else:
        if domain not in user.get_domains():
            user.add_domain_membership(domain, role_id=role_id, location_id=location_id,
                                       is_admin=False)
            user.save()
    return user


def add_location(user, location_id):
    if location_id:
        loc = Location.get(location_id)
        user.clear_locations()
        user.add_location(loc, create_sp_if_missing=True)


@retry(5)
def sync_ilsgateway_smsuser(domain, ilsgateway_smsuser):
    domain_part = "%s.commcarehq.org" % domain
    username_part = "%s%d" % (ilsgateway_smsuser.name.strip().replace(' ', '.').lower(), ilsgateway_smsuser.id)
    username = "%s@%s" % (username_part[:(128 - (len(domain_part) + 1))], domain_part)
    # sanity check
    assert len(username) <= 128
    user = CouchUser.get_by_username(username)
    splitted_value = ilsgateway_smsuser.name.split(' ', 1)
    first_name = last_name = ''
    if splitted_value:
        first_name = splitted_value[0][:30]
        last_name = splitted_value[1][:30] if len(splitted_value) > 1 else ''

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

    sp = SupplyPointCase.view('hqcase/by_domain_external_id',
                              key=[domain, str(ilsgateway_smsuser.supply_point)],
                              reduce=False,
                              include_docs=True,
                              limit=1).first()
    location_id = sp.location_id if sp else None

    if user is None and username_part:
        try:
            password = User.objects.make_random_password()
            user = CommCareUser.create(domain=domain, username=username, password=password,
                                       email=ilsgateway_smsuser.email, commit=False)
            user.first_name = first_name
            user.last_name = last_name
            user.is_active = bool(ilsgateway_smsuser.is_active)
            user.user_data = user_dict["user_data"]
            if "phone_numbers" in user_dict:
                user.set_default_phone_number(user_dict["phone_numbers"][0])
                try:
                    user.save_verified_number(domain, user_dict["phone_numbers"][0], True,
                                              ilsgateway_smsuser.backend)
                except PhoneNumberInUseException as e:
                    v = VerifiedNumber.by_phone(user_dict["phone_numbers"][0], include_pending=True)
                    v.delete()
                    user.save_verified_number(domain, user_dict["phone_numbers"][0], True,
                                              ilsgateway_smsuser.backend)
            dm = user.get_domain_membership(domain)
            dm.location_id = location_id
            user.save()
            add_location(user, location_id)

        except Exception as e:
            logging.error(e)
    else:
        dm = user.get_domain_membership(domain)
        current_location_id = dm.location_id if dm else None
        save = False

        if current_location_id != location_id:
            dm.location_id = location_id
            add_location(user, location_id)
            save = True

        if apply_updates(user, user_dict) or save:
            user.save()
    return user


def check_hashes(webuser, django_user, password):
    if webuser.password == password and django_user.password == password:
        return True
    else:
        logging.warning("Logistics: Hashes are not matching for user: %s" % webuser.username)
        return False


def resync_password(config, user):
    email = user.email
    password = user.password
    webuser = WebUser.get_by_username(email.lower())
    if not webuser:
        return

    django_user = webuser.get_django_user()
    domains = webuser.get_domains()
    if not domains:
        return None

    # Make sure that user is migrated and didn't exist before migration
    if all([config.for_domain(domain) is not None for domain in domains]):
        if force_to_datetime(user.date_joined).replace(microsecond=0) != webuser.date_joined:
            return None
        if not check_hashes(webuser, django_user, password):
            logging.info("Logistics: resyncing password...")
            webuser.password = password
            django_user.password = password
            webuser.save()
            django_user.save()


@retry(5)
def sync_ilsgateway_location(domain, endpoint, ilsgateway_location, fetch_groups=False):
    try:
        sql_loc = SQLLocation.objects.get(
            domain=domain,
            external_id=int(ilsgateway_location.id)
        )
        location = Location.get(sql_loc.location_id)
    except SQLLocation.DoesNotExist:
        location = None
    except SQLLocation.MultipleObjectsReturned:
        return

    if not location:
        if ilsgateway_location.parent_id:
            loc_parent = SupplyPointCase.view('hqcase/by_domain_external_id',
                                              key=[domain, str(ilsgateway_location.parent_id)],
                                              reduce=False,
                                              include_docs=True).first()
            if not loc_parent:
                parent = endpoint.get_location(ilsgateway_location.parent_id)
                loc_parent = sync_ilsgateway_location(domain, endpoint, Loc(parent))
            else:
                loc_parent = loc_parent.location
            location = Location(parent=loc_parent)
        else:
            location = Location()
            location.lineage = []
        location.domain = domain
        location.name = ilsgateway_location.name
        if ilsgateway_location.groups:
            location.metadata = {'groups': ilsgateway_location.groups}
        if ilsgateway_location.latitude:
            location.latitude = float(ilsgateway_location.latitude)
        if ilsgateway_location.longitude:
            location.longitude = float(ilsgateway_location.longitude)
        location.location_type = ilsgateway_location.type
        location.site_code = ilsgateway_location.code
        location.external_id = str(ilsgateway_location.id)
        location.save()
        if not SupplyPointCase.get_by_location(location):
            SupplyPointCase.create_from_location(domain, location)
    else:
        location_dict = {
            'name': ilsgateway_location.name,
            'latitude': float(ilsgateway_location.latitude) if ilsgateway_location.latitude else None,
            'longitude': float(ilsgateway_location.longitude) if ilsgateway_location.longitude else None,
            'location_type': ilsgateway_location.type,
            'site_code': ilsgateway_location.code.lower(),
            'external_id': str(ilsgateway_location.id),
            'metadata': {}
        }
        if ilsgateway_location.groups:
            location_dict['metadata']['groups'] = ilsgateway_location.groups
        case = SupplyPointCase.get_by_location(location)
        if apply_updates(location, location_dict):
            location.save()
            if case:
                case.update_from_location(location)
            else:
                SupplyPointCase.create_from_location(domain, location)
    if ilsgateway_location.historical_groups:
        historical_groups = ilsgateway_location.historical_groups
    elif fetch_groups:
        location_object = endpoint.get_location(
            ilsgateway_location.id,
            params=dict(with_historical_groups=1)
        )

        historical_groups = Loc(**location_object).historical_groups
    else:
        historical_groups = {}
    for date, groups in historical_groups.iteritems():
        for group in groups:
            HistoricalLocationGroup.objects.get_or_create(date=date, group=group,
                                                          location_id=location.sql_location)

    return location


def commtrack_settings_sync(project, locations_types):
    if MigrationCheckpoint.objects.filter(domain=project).count() != 0:
        return

    config = CommtrackConfig.for_domain(project)
    domain = Domain.get_by_name(project)
    domain.location_types = []
    for i, value in enumerate(locations_types):
        if not any(lt.name == value
                   for lt in domain.location_types):
            allowed_parents = [locations_types[i - 1]] if i > 0 else [""]

            domain.location_types.append(
                LocationType(
                    name=value,
                    allowed_parents=allowed_parents,
                    administrative=(value.lower() != 'facility')
                )
            )
    actions = [action.keyword for action in config.actions]
    if 'delivered' not in actions:
        config.actions.append(
            CommtrackActionConfig(
                action='receipts',
                keyword='delivered',
                caption='Delivered')
        )
    config.save()


def bootstrap_domain(config, endpoint, extensions=None, **kwargs):
    domain = config.domain
    start_date = datetime.today()
    endpoint = endpoint.from_config(config)
    try:
        checkpoint = MigrationCheckpoint.objects.get(domain=domain)
        api = checkpoint.api
        date = checkpoint.date
        limit = checkpoint.limit
        offset = checkpoint.offset
        if not checkpoint.start_date:
            checkpoint.start_date = start_date
            checkpoint.save()
        else:
            start_date = checkpoint.start_date
    except MigrationCheckpoint.DoesNotExist:
        checkpoint = MigrationCheckpoint()
        checkpoint.domain = domain
        checkpoint.start_date = start_date
        api = 'product'
        date = None
        limit = 1000
        offset = 0

    apis = [
        ('product', partial(products_sync, domain, endpoint, checkpoint, date=date, **kwargs)),
        ('location_facility', partial(locations_sync, domain, endpoint, checkpoint, date=date,
                                      filters=dict(date_updated__gte=date, type='facility'), **kwargs)),
        ('location_district', partial(locations_sync, domain, endpoint, checkpoint, date=date,
                                      filters=dict(date_updated__gte=date, type='district'), **kwargs)),
        ('location_region', partial(locations_sync, domain, endpoint, checkpoint, date=date,
                                    filters=dict(date_updated__gte=date, type='region'), **kwargs)),
        ('webuser', partial(webusers_sync, domain, endpoint, checkpoint, date=date,
                            filters=dict(user__date_joined__gte=date))),
        ('smsuser', partial(smsusers_sync, domain, endpoint, checkpoint, date=date,
                            filters=dict(date_updated__gte=date)))
    ]

    try:
        apis_from_checkpoint = itertools.dropwhile(lambda x: x[0] != api, apis)
        for api in apis_from_checkpoint:
            kwargs = dict(limit=limit, offset=offset)
            extension = extensions.get(api[0]) if extensions else None
            if extension:
                kwargs['extension'] = extension
            api[1](**kwargs)
            limit = 1000
            offset = 0

        save_checkpoint(checkpoint, 'product', 1000, 0, start_date, False)
        checkpoint.start_date = None
        checkpoint.save()
    except ConnectionError as e:
        logging.error(e)
