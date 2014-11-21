from celery.task import task
from casexml.apps.stock.models import StockReport, StockTransaction
from corehq.apps.commtrack.models import StockState, Product
from custom.ewsghana.api import GhanaEndpoint
from custom.ewsghana.extensions import ews_location_extension, ews_smsuser_extension, ews_webuser_extension, ews_product_extension
from custom.ewsghana.models import EWSGhanaConfig
from custom.logistics.commtrack import bootstrap_domain as ils_bootstrap_domain, \
    sync_ilsgateway_product, bootstrap_domain, commtrack_settings_sync
from custom.ilsgateway.tasks import get_locations, get_product_stock, get_stock_transaction


EXTENSIONS = {
    'product': ews_product_extension,
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
    endpoint = GhanaEndpoint.from_config(ewsghana_config)
    commtrack_settings_sync(domain, LOCATION_TYPES)
    for product in endpoint.get_products():
        sync_ilsgateway_product(domain, product)
    get_locations(domain, endpoint, EWS_FACILITIES)
    get_product_stock(domain, endpoint, EWS_FACILITIES)
    get_stock_transaction(domain, endpoint, EWS_FACILITIES)


@task
def ews_clear_stock_data_task():
    StockTransaction.objects.filter(report__domain='ewsghana-test-1').delete()
    StockReport.objects.filter(domain='ewsghana-test-1').delete()
    products = Product.ids_by_domain('ewsghana-test-1')
    StockState.objects.filter(product_id__in=products).delete()
