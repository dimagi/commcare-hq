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
from custom.api.utils import apply_updates
from corehq.apps.commtrack.models import SupplyPointCase, CommTrackUser, CommtrackConfig, LocationType, \
    CommtrackActionConfig
from corehq.apps.products.models import Product
from custom.logistics.models import MigrationCheckpoint
from dimagi.utils.dates import force_to_datetime
from custom.ilsgateway.models import HistoricalLocationGroup
from requests.exceptions import ConnectionError
from datetime import datetime
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


def synchronization(name, get_objects_function, sync_function, checkpoint, date, limit, offset, **kwargs):
    has_next = True
    next_url = ""

    while has_next:
        meta, objects = get_objects_function(next_url_params=next_url, limit=limit, offset=offset, **kwargs)
        save_checkpoint(checkpoint, name,
                        meta.get('limit') or limit, meta.get('offset') or offset,
                        date)
        for obj in objects:
            sync_function(obj)
        has_next, next_url = get_next_meta_url(has_next, meta, next_url)


def save_checkpoint(checkpoint, api, limit, offset, date, commit=True):
    checkpoint.limit = limit
    checkpoint.offset = offset
    checkpoint.api = api
    checkpoint.date = date
    if commit:
        checkpoint.save()


def save_stock_data_checkpoint(checkpoint, api, limit, offset, date, external_id, commit=True):
    save_checkpoint(checkpoint, api, limit, offset, date, False)
    if external_id:
        try:
            location = SQLLocation.objects.get(domain=checkpoint.domain, external_id=int(external_id))
        except SQLLocation.DoesNotExist:
            return
        checkpoint.location = location
    else:
        checkpoint.location = None
    if commit:
        checkpoint.save()


def add_location(user, location_id):
    commtrack_user = CommTrackUser.wrap(user.to_json())
    if location_id:
        loc = Location.get(location_id)
        commtrack_user.clear_locations()
        commtrack_user.add_location(loc, create_sp_if_missing=True)


def bootstrap_domain(api_object, **kwargs):
    domain = api_object.domain
    endpoint = api_object.endpoint
    start_date = datetime.today()

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
        api_object.prepare_commtrack_config()
        checkpoint = MigrationCheckpoint()
        checkpoint.domain = domain
        checkpoint.start_date = start_date
        api = 'product'
        date = None
        limit = 100
        offset = 0

    synchronize_domain = partial(synchronization, checkpoint=checkpoint, date=date)
    apis = [
        ('product', partial(
            synchronize_domain,
            get_objects_function=endpoint.get_products,
            sync_function=api_object.products_sync
        )),
        ('location_facility', partial(
            synchronize_domain,
            get_objects_function=endpoint.get_locations,
            sync_function=api_object.locations_sync,
            fetch_groups=True,
            filters=dict(date_updated__gte=date, type='facility', is_active=True)
        )),
        ('location_district', partial(
            synchronize_domain,
            get_objects_function=endpoint.get_locations,
            sync_function=api_object.locations_sync,
            fetch_groups=True,
            filters=dict(date_updated__gte=date, type='district', is_active=True)
        )),
        ('location_region', partial(
            synchronize_domain,
            get_objects_function=endpoint.get_locations,
            sync_function=api_object.locations_sync,
            fetch_groups=True,
            filters=dict(date_updated__gte=date, type='region', is_active=True)
        )),
        ('webuser', partial(
            synchronize_domain,
            get_objects_function=endpoint.get_webusers,
            sync_function=api_object.web_users_sync,
            filters=dict(user__date_joined__gte=date)
        )),
        ('smsuser', partial(
            synchronize_domain,
            get_objects_function=endpoint.get_smsusers,
            sync_function=api_object.sms_users_sync,
            filters=dict(date_updated__gte=date)
        ))
    ]

    try:
        apis_from_checkpoint = itertools.dropwhile(lambda x: x[0] != api, apis)
        for (api_name, api_function) in apis_from_checkpoint:
            api_function(name=api_name, limit=limit, offset=offset, **kwargs)
            limit = 100
            offset = 0

        save_checkpoint(checkpoint, 'product', 100, 0, start_date, False)
        checkpoint.start_date = None
        checkpoint.save()
    except ConnectionError as e:
        logging.error(e)
