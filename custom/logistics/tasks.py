from datetime import datetime
import itertools
from corehq.apps.commtrack.models import SupplyPointCase
from corehq.apps.locations.models import SQLLocation
from custom.ilsgateway import TEST
from custom.logistics.commtrack import save_stock_data_checkpoint
from custom.logistics.models import StockDataCheckpoint
from celery.task.base import task
import logging
from custom.logistics.commtrack import resync_password


@task
def stock_data_task(domain, endpoint, apis, test_facilities=None):
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
        supply_point = SupplyPointCase.view(
            'commtrack/supply_point_by_loc',
            key=[location.domain, location.location_id],
            include_docs=True,
            classes={'CommCareCase': SupplyPointCase},
        ).one()
        external_id = supply_point.external_id if supply_point else None
        if external_id:
            facilities = itertools.dropwhile(lambda x: int(x) != int(external_id), facilities)

    for idx, api in enumerate(apis_from_checkpoint):
        api[1](
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
        if idx == 0:
            facilities = facilities_copy
    save_stock_data_checkpoint(checkpoint, 'product_stock', 100, 0, start_date, None, False)
    checkpoint.start_date = None
    checkpoint.save()


@task
def resync_webusers_passwords_task(config, endpoint):
    logging.info("Logistics: Webusers passwords resyncing started")
    _, webusers = endpoint.get_webusers(limit=2000)

    for webuser in webusers:
        resync_password(config, webuser)

    logging.info("Logistics: Webusers passwords resyncing finished")
