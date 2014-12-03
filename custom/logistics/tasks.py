from datetime import datetime
import itertools
from celery.task import task
from corehq.apps.locations.models import SQLLocation
from custom.ilsgateway import TEST
from custom.ilsgateway.tasks import get_locations
from custom.logistics.commtrack import commtrack_settings_sync, sync_ilsgateway_product, save_stock_data_checkpoint
from custom.logistics.models import StockDataCheckpoint


@task
def stock_data_task(domain, endpoint, apis, location_types, test_facilities=None):
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
        if StockDataCheckpoint.objects.filter(domain=domain).count() == 0:
            commtrack_settings_sync(domain, location_types)
            get_locations(domain, endpoint, facilities)
            for product in endpoint.get_products():
                sync_ilsgateway_product(domain, product)
    else:
        facilities = SQLLocation.objects.filter(
            domain=domain,
            location_type__iexact='FACILITY'
        ).order_by('created_at').values_list('external_id', flat=True)

    apis_from_checkpoint = itertools.dropwhile(lambda x: x[0] != api, apis)
    facilities_copy = list(facilities)
    if location:
        facilities = itertools.dropwhile(lambda x: int(x) != int(location.external_id), facilities)

    for idx, api in enumerate(apis_from_checkpoint):
        api[1](
            domain=domain,
            checkpoint=checkpoint,
            date=date,
            start_date=start_date,
            limit=limit,
            offset=offset,
            endpoint=endpoint,
            facilities=facilities
        )
        limit = 100
        offset = 0
        if idx == 0:
            facilities = facilities_copy

    save_stock_data_checkpoint(checkpoint, 'product_stock', 100, 0, start_date, None, False)
    checkpoint.start_date = None
    checkpoint.save()
