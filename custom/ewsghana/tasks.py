from celery.schedules import crontab
from celery.task import task, periodic_task
from casexml.apps.stock.models import StockReport, StockTransaction
from corehq.apps.users.models import CommCareUser
from custom.ewsghana.api import EWSApi

from corehq.apps.commtrack.models import StockState, Product

from custom.ewsghana.api import GhanaEndpoint
from custom.ewsghana.extensions import ews_location_extension, ews_smsuser_extension, ews_webuser_extension, \
    ews_product_extension
from custom.ewsghana.models import EWSGhanaConfig
from custom.ewsghana.stock_data import EWSStockDataSynchronization
from custom.logistics.commtrack import bootstrap_domain as ews_bootstrap_domain, \
    bootstrap_domain
from custom.logistics.models import StockDataCheckpoint
from custom.logistics.tasks import stock_data_task
import settings


EXTENSIONS = {
    'product': ews_product_extension,
    'location_facility': ews_location_extension,
    'location_district': ews_location_extension,
    'location_region': ews_location_extension,
    'webuser': ews_webuser_extension,
    'smsuser': ews_smsuser_extension
}


# Region Greater Accra
EWS_FACILITIES = [304, 324, 330, 643, 327, 256, 637, 332, 326, 338, 340, 331, 347, 27, 975, 346, 477, 344, 339,
                  458, 748, 18, 379, 456, 644, 462, 459, 475, 638, 969, 480, 464, 960, 529, 255, 16, 31, 639, 640,
                  11, 15, 25, 645, 95, 13, 970, 952, 470, 971, 474, 962, 479, 953, 457, 476, 481, 501, 500, 499,
                  503, 502, 498, 496, 497, 10, 333, 963, 335, 972, 914, 527, 26, 531, 469, 530, 523, 19, 915, 524,
                  528, 325, 20, 460, 468, 916, 646, 519, 345, 471, 633, 518, 642, 328, 343, 21, 467, 648, 334, 473,
                  6, 342, 28, 478, 472, 955, 964, 636, 258, 918, 466, 337, 956, 809, 965, 24, 974, 957, 954, 22,
                  29, 958, 967, 917, 951, 515, 8, 959, 968, 649, 966, 341, 336, 647, 973, 5, 517, 522, 465, 635,
                  526, 4, 30, 1, 14, 23, 521, 532, 516, 461, 520, 525, 961, 641, 257, 348]


@periodic_task(run_every=crontab(hour="23", minute="55", day_of_week="*"),
               queue=getattr(settings, 'CELERY_PERIODIC_QUEUE', 'celery'))
def migration_task():
    for config in EWSGhanaConfig.get_all_steady_sync_configs():
        if config.enabled:
            endpoint = GhanaEndpoint.from_config(config)
            ews_bootstrap_domain(EWSApi(config.domain, endpoint))
            stock_data_task.delay(EWSStockDataSynchronization(config.domain, endpoint))


@task(queue='background_queue')
def ews_bootstrap_domain_task(domain):
    ews_config = EWSGhanaConfig.for_domain(domain)
    return bootstrap_domain(EWSApi(domain, GhanaEndpoint.from_config(ews_config)))


@task(queue='background_queue', ignore_result=True)
def ews_clear_stock_data_task(domain):
    StockTransaction.objects.filter(report__domain=domain).delete()
    StockReport.objects.filter(domain=domain).delete()
    products = Product.ids_by_domain(domain)
    StockState.objects.filter(product_id__in=products).delete()


@task(queue='background_queue', ignore_result=True)
def delete_last_migrated_stock_data(domain):
    checkpoint = StockDataCheckpoint.objects.get(domain=domain)
    StockReport.objects.filter(domain=domain, date__gte=checkpoint.date).delete()
    checkpoint.location = None
    checkpoint.offset = 0
    checkpoint.api = 'stock_transaction'
    checkpoint.start_date = None
    checkpoint.save()


@task(queue='background_queue', ignore_result=True)
def convert_user_data_fields_task(domain):
    for user in CommCareUser.by_domain(domain):
        if isinstance(user.user_data.get('role'), basestring):
            user.user_data['role'] = [user.user_data['role']]
            user.save()
