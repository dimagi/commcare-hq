import itertools
import logging
import traceback
from django.db import transaction

from corehq.apps.locations.models import Location, SQLLocation
from custom.logistics.models import MigrationCheckpoint
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


def synchronization(api_sync_object, checkpoint, date, limit, offset, params=None, atomic=False, **kwargs):
    has_next = True
    next_url = ""
    params = params or {}
    while has_next:
        meta, objects = api_sync_object.get_objects_function(
            next_url_params=next_url,
            limit=limit,
            offset=offset,
            filters=api_sync_object.filters,
            **kwargs
        )
        if checkpoint:
            save_checkpoint(checkpoint, api_sync_object.name,
                            meta.get('limit') or limit, meta.get('offset') or offset,
                            date)
        if atomic:
            with transaction.atomic():
                for obj in objects:
                    api_sync_object.sync_function(obj, **params)
        else:
            for obj in objects:
                api_sync_object.sync_function(obj, **params)

        has_next, next_url = get_next_meta_url(has_next, meta, next_url)


def save_checkpoint(checkpoint, api, limit, offset, date, commit=True):
    checkpoint.limit = limit
    checkpoint.offset = offset
    checkpoint.api = api
    checkpoint.date = date
    if commit:
        checkpoint.save()


def save_stock_data_checkpoint(checkpoint, api, limit, offset, date, location_id, commit=True):
    save_checkpoint(checkpoint, api, limit, offset, date, False)
    if location_id:
        checkpoint.location = SQLLocation.objects.get(location_id=location_id)
    else:
        checkpoint.location = None
    if commit:
        checkpoint.save()


def add_location(user, location_id):
    if location_id:
        loc = Location.get(location_id)
        user.clear_location_delegates()
        user.add_location_delegate(loc)


def check_hashes(webuser, django_user, password):
    if webuser.password == password and django_user.password == password:
        return True
    else:
        logging.warning("Logistics: Hashes are not matching for user: %s" % webuser.username)
        return False


def bootstrap_domain(api_object, **kwargs):
    domain = api_object.domain
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
    apis = api_object.apis

    try:
        apis_from_checkpoint = itertools.dropwhile(lambda x: x.name != api, apis)
        for api in apis_from_checkpoint:
            if date and api.migrate_once:
                continue
            api.add_date_filter(date)
            synchronization(api, checkpoint, date, limit, offset, **kwargs)
            limit = 100
            offset = 0

        save_checkpoint(checkpoint, 'product', 100, 0, checkpoint.start_date, False)
        checkpoint.start_date = None
        checkpoint.save()
        from custom.ilsgateway.tasks import balance_migration_task
        balance_migration_task.delay(api_object.domain, api_object.endpoint)
    except ConnectionError as e:
        logging.error(e)
