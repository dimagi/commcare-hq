from celery.task import task
from casexml.apps.stock.models import StockReport, StockTransaction
from custom.ewsghana.api import EWSApi

from corehq.apps.commtrack.models import StockState, Product

from custom.ewsghana.api import GhanaEndpoint
from custom.ewsghana.extensions import ews_location_extension, ews_smsuser_extension, ews_webuser_extension, \
    ews_product_extension
from custom.ewsghana.models import EWSGhanaConfig
from custom.logistics.commtrack import bootstrap_domain as ews_bootstrap_domain, \
    bootstrap_domain


EXTENSIONS = {
    'product': ews_product_extension,
    'location_facility': ews_location_extension,
    'location_district': ews_location_extension,
    'location_region': ews_location_extension,
    'webuser': ews_webuser_extension,
    'smsuser': ews_smsuser_extension
}


# District Ashanti
EWS_FACILITIES = [109, 110, 624, 626, 922, 908, 961, 948, 956, 967]


# @periodic_task(run_every=timedelta(days=1), queue=getattr(settings, 'CELERY_PERIODIC_QUEUE', 'celery'))
def migration_task():
    configs = EWSGhanaConfig.get_all_configs()
    for config in configs:
        if config.enabled:
            ews_bootstrap_domain(EWSApi(config.domain, GhanaEndpoint.from_config(config)))


@task
def ews_bootstrap_domain_task(domain):
    ews_config = EWSGhanaConfig.for_domain(domain)
    return bootstrap_domain(EWSApi(domain, GhanaEndpoint.from_config(ews_config)))


@task
def ews_clear_stock_data_task():
    StockTransaction.objects.filter(report__domain='ewsghana-test-1').delete()
    StockReport.objects.filter(domain='ewsghana-test-1').delete()
    products = Product.ids_by_domain('ewsghana-test-1')
    StockState.objects.filter(product_id__in=products).delete()
