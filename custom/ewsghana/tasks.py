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
EWS_FACILITIES = [770, 777, 12, 27, 30, 33, 35, 36, 778, 14, 19, 25, 16, 24, 11, 26, 29, 17, 38, 32, 37, 34, 102,
                  28, 18, 15, 23, 22, 21, 779, 772, 360, 358, 359, 773, 440, 441, 442, 444, 445, 446, 447, 449,
                  453, 455, 456, 457, 458, 459, 462, 464, 782, 460, 454, 466, 451, 439, 448, 780, 596,
                  13, 774, 443, 510, 595, 598, 587, 592, 588, 593, 589, 590, 599, 600, 601, 602, 603, 604, 605,
                  606, 607, 609, 610, 775, 615, 633, 608, 612, 656, 657, 660, 662, 663, 664, 665, 629, 630, 631,
                  635, 636, 632, 591, 634, 614, 651, 648, 653, 659, 654, 655, 658, 652, 661, 611, 776, 20, 781,
                  613, 649, 650, 768, 771, 944, 594, 461, 31, 1044, 1069, 1070, 1071, 1072, 1073, 1104, 1105,
                  1106, 1107, 1108, 1109, 1110, 1111, 1112, 1113, 1114, 1115, 1116, 1117, 1118, 1119, 1120,
                  1121, 1122, 1123, 1124, 1125, 1212]


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
