from datetime import datetime
from functools import partial
import itertools
from corehq.apps.commtrack.models import SupplyPointCase
from corehq.apps.locations.models import SQLLocation, Location
from custom.ilsgateway import TEST
from custom.logistics.commtrack import save_stock_data_checkpoint, synchronization
from custom.logistics.models import StockDataCheckpoint
from celery.task.base import task


def get_or_create_checkpoint(domain):
    try:
        checkpoint = StockDataCheckpoint.objects.get(domain=domain)
        if not checkpoint.start_date:
            checkpoint.start_date = datetime.today()
            checkpoint.save()
        return checkpoint, False
    except StockDataCheckpoint.DoesNotExist:
        return StockDataCheckpoint(
            domain=domain,
            date=None,
            start_date=datetime.today(),
            api='product_stock',
            limit=100,
            offset=0,
            location=None,
        ), True


@task
def stock_data_task(domain, endpoint, apis, test_facilities=None):
    if TEST:
        facilities = test_facilities
    else:
        facilities = SQLLocation.objects.filter(
            domain=domain,
            location_type__iexact='FACILITY'
        ).order_by('created_at').values_list('external_id', flat=True)

    facilities_copy = list(facilities)

    # checkpoint logic
    checkpoint, created = get_or_create_checkpoint(domain)
    if not created:
        # filter apis, location, etc. form checkpoint data
        apis = itertools.dropwhile(lambda x: x[0] != checkpoint.api, apis)
        if checkpoint.location:
            supply_point = SupplyPointCase.view(
                'commtrack/supply_point_by_loc',
                key=[checkpoint.location.domain, checkpoint.location.location_id],
                include_docs=True,
                classes={'CommCareCase': SupplyPointCase},
            ).one()
            external_id = supply_point.external_id if supply_point else None
            if external_id:
                facilities = itertools.dropwhile(lambda x: int(x) != int(external_id), facilities)

    limit = checkpoint.limit
    offset = checkpoint.offset
    for idx, (api_name, api_function) in enumerate(apis):
        api_function(
            domain=domain,
            checkpoint=checkpoint,
            date=checkpoint.date,
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
    save_stock_data_checkpoint(checkpoint, 'product_stock', 100, 0, None, None)


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
