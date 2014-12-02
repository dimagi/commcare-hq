from datetime import datetime
from functools import partial
from celery.task import task
from casexml.apps.stock.models import StockReport, StockTransaction
import itertools
from corehq.apps.commtrack.models import StockState, Product
from corehq.apps.locations.models import SQLLocation
from custom.ewsghana import TEST
from custom.ewsghana.api import GhanaEndpoint
from custom.ewsghana.extensions import ews_location_extension, ews_smsuser_extension, ews_webuser_extension
from custom.ewsghana.models import EWSGhanaConfig
from custom.logistics.commtrack import bootstrap_domain as ils_bootstrap_domain, \
    sync_ilsgateway_product, bootstrap_domain, commtrack_settings_sync, save_stock_data_checkpoint
from custom.ilsgateway.tasks import get_locations, get_product_stock, get_stock_transaction
from custom.logistics.models import StockDataCheckpoint


EXTENSIONS = {
    'location_facility': ews_location_extension,
    'location_district': ews_location_extension,
    'location_region': ews_location_extension,
    'webuser': ews_webuser_extension,
    'smsuser': ews_smsuser_extension
}


LOCATION_TYPES = ["country", "region", "district", "facility"]


# @periodic_task(run_every=timedelta(days=1), queue=getattr(settings, 'CELERY_PERIODIC_QUEUE', 'celery'))
def migration_task():
    configs = EWSGhanaConfig.get_all_configs()
    for config in configs:
        if config.enabled:
            commtrack_settings_sync(config.domain, LOCATION_TYPES)
            ils_bootstrap_domain(config, GhanaEndpoint.from_config(config), EXTENSIONS)


@task
def ews_bootstrap_domain_task(domain):
    ews_config = EWSGhanaConfig.for_domain(domain)
    commtrack_settings_sync(domain, LOCATION_TYPES)
    return bootstrap_domain(ews_config, GhanaEndpoint.from_config(ews_config), EXTENSIONS, fetch_groups=False)

# District Ashanti
EWS_FACILITIES = [109, 110, 624, 626, 922, 908, 961, 948, 956, 967]


@task
def ews_stock_data_task(domain):
    ewsghana_config = EWSGhanaConfig.for_domain(domain)
    domain = ewsghana_config.domain

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

    endpoint = GhanaEndpoint.from_config(ewsghana_config)
    if TEST:
        commtrack_settings_sync(domain, LOCATION_TYPES)
        for product in endpoint.get_products():
            sync_ilsgateway_product(domain, product)
        get_locations(domain, endpoint, EWS_FACILITIES)
        facilities = EWS_FACILITIES
    else:
        facilities = SQLLocation.objects.filter(
            domain=domain,
            location_type__iexact='FACILITY'
        ).order_by('created_at').values_list('external_id', flat=True)
    apis = (
        ('product_stock', partial(get_product_stock, domain=domain, endpoint=endpoint,
                                  checkpoint=checkpoint, date=date, start_date=start_date)),
        ('stock_transaction', partial(get_stock_transaction, domain=domain, endpoint=endpoint,
                                      checkpoint=checkpoint, date=date, start_date=start_date))
    )
    apis_from_checkpoint = itertools.dropwhile(lambda x: x[0] != api, apis)
    facilities_copy = list(facilities)
    if location:
        facilities = itertools.dropwhile(lambda x: int(x) != int(location.external_id), facilities)
    else:
        facilities = facilities
    for idx, api in enumerate(apis_from_checkpoint):
        print api[0], limit, offset
        api[1](limit=limit, offset=offset, facilities=facilities)
        limit = 100
        offset = 0
        if idx == 0:
            facilities = facilities_copy

    save_stock_data_checkpoint(checkpoint, 'product_stock', 100, 0, start_date, None, False)
    checkpoint.start_date = None
    checkpoint.save()


@task
def ews_clear_stock_data_task():
    StockTransaction.objects.filter(report__domain='ewsghana-test-1').delete()
    StockReport.objects.filter(domain='ewsghana-test-1').delete()
    products = Product.ids_by_domain('ewsghana-test-1')
    StockState.objects.filter(product_id__in=products).delete()
