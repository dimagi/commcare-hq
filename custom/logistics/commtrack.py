import itertools
from functools import partial
import logging
import traceback
from corehq.apps.commtrack.models import SupplyPointCase

from corehq.apps.locations.models import Location
from corehq.apps.users.models import WebUser
from custom.logistics.models import MigrationCheckpoint
from dimagi.utils.dates import force_to_datetime
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
        if checkpoint:
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
        supply_point = SupplyPointCase.view('hqcase/by_domain_external_id',
                                            key=[checkpoint.domain, str(external_id)],
                                            reduce=False,
                                            include_docs=True).first()
        if not supply_point:
            return
        checkpoint.location = supply_point.location.sql_location
    else:
        checkpoint.location = None
    if commit:
        checkpoint.save()


def add_location(user, location_id):
    if location_id:
        loc = Location.get(location_id)
        user.clear_location_delgates()
        user.add_location_delegate(loc)


def check_hashes(webuser, django_user, password):
    if webuser.password == password and django_user.password == password:
        return True
    else:
        logging.warning("Logistics: Hashes are not matching for user: %s" % webuser.username)
        return False


def bootstrap_domain(api_object, **kwargs):
    domain = api_object.domain
    endpoint = api_object.endpoint
    start_date = datetime.today()

    # get the last saved checkpoint from a prior migration and various config options
    try:
        checkpoint = MigrationCheckpoint.objects.get(domain=domain)
        api = checkpoint.api
        date = checkpoint.date
        limit = 100
        offset = checkpoint.offset
        if not checkpoint.start_date:
            checkpoint.start_date = start_date
            checkpoint.save()
        else:
            start_date = checkpoint.start_date
    except MigrationCheckpoint.DoesNotExist:
        # bootstrap static domain data
        api_object.prepare_commtrack_config()
        checkpoint = MigrationCheckpoint()
        checkpoint.domain = domain
        checkpoint.start_date = start_date
        api = 'product'
        date = None
        limit = 100
        offset = 0
    api_object.set_default_backend()
    api_object.prepare_custom_fields()
    api_object.create_or_edit_roles()
    synchronize_domain = partial(synchronization, checkpoint=checkpoint, date=date)
    apis = [
        ('product', partial(
            synchronize_domain,
            get_objects_function=endpoint.get_products,
            sync_function=api_object.product_sync
        )),
        ('location_region', partial(
            synchronize_domain,
            get_objects_function=endpoint.get_locations,
            sync_function=api_object.location_sync,
            fetch_groups=True,
            filters=dict(date_updated__gte=date, type='region', is_active=True)
        )),
        ('location_district', partial(
            synchronize_domain,
            get_objects_function=endpoint.get_locations,
            sync_function=api_object.location_sync,
            fetch_groups=True,
            filters=dict(date_updated__gte=date, type='district', is_active=True)
        )),
        ('location_facility', partial(
            synchronize_domain,
            get_objects_function=endpoint.get_locations,
            sync_function=api_object.location_sync,
            fetch_groups=True,
            filters=dict(date_updated__gte=date, type='facility', is_active=True)
        )),
        ('webuser', partial(
            synchronize_domain,
            get_objects_function=endpoint.get_webusers,
            sync_function=api_object.web_user_sync,
            filters=dict(user__date_joined__gte=date)
        )),
        ('smsuser', partial(
            synchronize_domain,
            get_objects_function=endpoint.get_smsusers,
            sync_function=api_object.sms_user_sync,
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
