from datetime import datetime
from functools import partial
import itertools
from corehq.apps.commtrack.models import SupplyPointCase
from corehq.apps.locations.models import SQLLocation, Location
from custom.ilsgateway import TEST
from custom.logistics.commtrack import save_stock_data_checkpoint, synchronization
from custom.logistics.models import StockDataCheckpoint
from celery.task.base import task


@task
def stock_data_task(domain, endpoint, apis, test_facilities=None):
    # checkpoint logic
    start_date = datetime.today()
    try:
        checkpoint = StockDataCheckpoint.objects.get(domain=domain)
        api = checkpoint.api
        date = checkpoint.date
        limit = checkpoint.limit
        offset = checkpoint.offset
        location = checkpoint.location
        if not checkpoint.start_date:
            checkpoint.start_date = start_date
            checkpoint.save()
        else:
            start_date = checkpoint.start_date
    except StockDataCheckpoint.DoesNotExist:
        checkpoint = StockDataCheckpoint()
        checkpoint.domain = domain
        checkpoint.start_date = start_date
        api = 'product_stock'
        date = None
        limit = 100
        offset = 0
        location = None

    if TEST:
        facilities = test_facilities
    else:
        facilities = SQLLocation.objects.filter(
            domain=domain,
            location_type__iexact='FACILITY'
        ).order_by('created_at').values_list('external_id', flat=True)

    apis_from_checkpoint = itertools.dropwhile(lambda x: x[0] != api, apis)
    facilities_copy = list(facilities)
    if location:
        supply_point = SupplyPointCase.get_by_location_id(domain, location.location_id)
        external_id = supply_point.external_id if supply_point else None
        if external_id:
            facilities = itertools.dropwhile(lambda x: int(x) != int(external_id), facilities)

    for idx, (api_name, api_function) in enumerate(apis_from_checkpoint):
        api_function(
            domain=domain,
            checkpoint=checkpoint,
            date=date,
            limit=limit,
            offset=offset,
            endpoint=endpoint,
            facilities=facilities
        )
        limit = 100
        offset = 0
        # todo: see if we can avoid modifying the list of facilities in place
        if idx == 0:
            facilities = facilities_copy
    save_stock_data_checkpoint(checkpoint, 'product_stock', 100, 0, start_date, None, False)
    checkpoint.start_date = None
    checkpoint.save()


@task
def sms_users_fix(api):
    endpoint = api.endpoint
    api.set_default_backend()
    synchronization(None, endpoint.get_smsusers, partial(api.add_language_to_user),
                    None, None, 100, 0)


@task
def locations_fix(domain):
    locations = SQLLocation.objects.filter(domain=domain, location_type__in=['country', 'region', 'district'])
    for loc in locations:
        sp = Location.get(loc.location_id).linked_supply_point()
        if sp:
            sp.external_id = None
            sp.save()
        else:
            fake_location = Location(
                _id=loc.location_id,
                name=loc.name,
                domain=domain
            )
            SupplyPointCase.get_or_create_by_location(fake_location)


@task
def add_products_to_loc(api):
    endpoint = api.endpoint
    synchronization(None, endpoint.get_locations, api.location_sync, None, None, 100, 0,
                    filters={"is_active": True})
