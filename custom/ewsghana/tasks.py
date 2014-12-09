from celery.task import task
from casexml.apps.stock.models import StockReport, StockTransaction
from corehq.apps.commtrack.models import StockState, Product, SupplyPointCase
from corehq.apps.consumption.const import DAYS_IN_MONTH
from corehq.apps.products.models import SQLProduct
from custom.ewsghana.api import GhanaEndpoint
from custom.ewsghana.extensions import ews_location_extension, ews_smsuser_extension, ews_webuser_extension, \
    ews_product_extension
from custom.ewsghana.models import EWSGhanaConfig
from custom.logistics.commtrack import bootstrap_domain as ils_bootstrap_domain, \
    sync_ilsgateway_product, bootstrap_domain, commtrack_settings_sync
from custom.ilsgateway.tasks import get_locations, get_stock_transaction


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


def get_product_stock(domain, endpoint, facilities):
    for facility in facilities:
        has_next = True
        next_url = ""
        while has_next:
            meta, product_stocks = endpoint.get_productstocks(next_url_params=next_url,
                                                              filters=dict(supply_point=facility))
            for product_stock in product_stocks:
                case = SupplyPointCase.view('hqcase/by_domain_external_id',
                                            key=[domain, str(product_stock.supply_point)],
                                            reduce=False,
                                            include_docs=True,
                                            limit=1).first()
                product = Product.get_by_code(domain, product_stock.product)
                try:
                    stock_state = StockState.objects.get(section_id='stock',
                                                         case_id=case._id,
                                                         product_id=product._id)
                except StockState.DoesNotExist:
                    stock_state = StockState(section_id='stock',
                                             case_id=case._id,
                                             product_id=product._id,
                                             stock_on_hand=product_stock.quantity or 0,
                                             last_modified_date=product_stock.last_modified,
                                             sql_product=SQLProduct.objects.get(product_id=product._id))

                if product_stock.auto_monthly_consumption:
                    stock_state.daily_consumption = product_stock.auto_monthly_consumption / DAYS_IN_MONTH
                elif product_stock.use_auto_consumption is False:
                    stock_state.daily_consumption = product_stock.manual_monthly_consumption / DAYS_IN_MONTH
                else:
                    stock_state.daily_consumption = None

                stock_state.save()

            if not meta.get('next', False):
                has_next = False
            else:
                next_url = meta['next'].split('?')[1]


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
