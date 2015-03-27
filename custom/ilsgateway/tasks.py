from datetime import datetime
import logging
from celery.schedules import crontab

from celery.task import task, periodic_task
from django.db import transaction
from psycopg2._psycopg import DatabaseError

from casexml.apps.stock.models import StockReport, StockTransaction
from corehq.apps.commtrack.models import StockState
from corehq.apps.products.models import Product
from custom.ilsgateway.api import ILSGatewayEndpoint, ILSGatewayAPI
from custom.logistics.commtrack import bootstrap_domain as ils_bootstrap_domain, save_stock_data_checkpoint
from custom.ilsgateway.models import ILSGatewayConfig, SupplyPointStatus, DeliveryGroupReport, ReportRun
from custom.ilsgateway.tanzania.warehouse_updater import populate_report_data
from custom.logistics.tasks import stock_data_task, sync_stock_transactions


@periodic_task(run_every=crontab(hour="23", minute="55", day_of_week="*"),
               queue='background_queue')
def migration_task():
    for config in ILSGatewayConfig.get_all_steady_sync_configs():
        if config.enabled:
            endpoint = ILSGatewayEndpoint.from_config(config)
            ils_bootstrap_domain(ILSGatewayAPI(config.domain, endpoint))
            apis = get_ilsgateway_data_migrations()
            stock_data_task.delay(config.domain, endpoint, apis, config, ILS_FACILITIES)


@task(queue='background_queue')
def ils_bootstrap_domain_task(domain):
    ils_config = ILSGatewayConfig.for_domain(domain)
    return ils_bootstrap_domain(ILSGatewayAPI(domain, ILSGatewayEndpoint.from_config(ils_config)))


def get_ilsgateway_data_migrations():
    """
    Returns a tuple of (api_name, migration_function) tuples relevant to the ILSGateway migration
    for use in the stock_data_task.
    """
    return (
        ('stock_transaction', sync_stock_transactions),
        ('supply_point_status', get_supply_point_statuses),
        ('delivery_group', get_delivery_group_reports)
    )

# Region KILIMANJARO
ILS_FACILITIES = [948, 998, 974, 1116, 971, 1122, 921, 658, 995, 1057,
                  652, 765, 1010, 657, 1173, 1037, 965, 749, 1171, 980,
                  1180, 1033, 975, 1056, 970, 742, 985, 2194, 935, 1128,
                  1172, 773, 916, 1194, 4862, 1003, 994, 1034, 1113, 1167,
                  949, 987, 986, 960, 1046, 942, 972, 21, 952, 930,
                  1170, 1067, 1006, 752, 747, 1176, 746, 755, 1102, 924,
                  744, 1109, 760, 922, 945, 988, 927, 1045, 1060, 938,
                  1041, 1101, 1107, 939, 910, 934, 929, 1111, 1174, 1044,
                  1008, 914, 1040, 1035, 1126, 1203, 912, 990, 908, 654,
                  1051, 1110, 983, 771, 1068, 756, 4807, 973, 1013, 911,
                  1048, 1196, 917, 1127, 963, 1032, 1164, 951, 918, 999,
                  923, 1049, 1000, 1165, 915, 1036, 1121, 758, 1054, 1042,
                  4861, 1007, 1053, 954, 761, 1002, 748, 919, 976, 1177,
                  1179, 1001, 743, 762, 741, 959, 1119, 772, 941, 956, 964,
                  1014, 953, 754, 1202, 1166, 977, 757, 961, 759, 997, 947, 1112, 978, 1124,
                  768, 937, 1195, 913, 906, 1043, 1178, 992, 1038, 957, 1106, 767, 979, 1012,
                  926, 1120, 933, 1066, 1105, 943, 1047, 1063, 1004, 958, 751, 763, 1011, 936,
                  1114, 932, 984, 656, 653, 946, 1058, 931, 770, 1108, 909, 1118, 1062, 745, 1065,
                  955, 1052, 753, 944, 1061, 1069, 1104, 996, 4860, 950, 993, 1064, 1175, 1059, 1050,
                  968, 928, 989, 967, 966, 750, 981, 1055, 766, 1123, 1039, 1103, 655, 1125, 774, 991,
                  1117, 920, 769, 1005, 1009, 925, 1115, 907, 4996]


def get_locations(api_object, facilities):
    for facility in facilities:
        location = api_object.endpoint.get_location(facility, params=dict(with_historical_groups=1))
        api_object.location_sync(api_object.endpoint.models_map['location'](location))


def sync_supply_point_status(domain, endpoint, facility, checkpoint, date, limit=100, offset=0):
    has_next = True
    next_url = ""

    while has_next:
        meta, supply_point_statuses = endpoint.get_supplypointstatuses(
            domain,
            limit=limit,
            offset=offset,
            next_url_params=next_url,
            filters=dict(supply_point=facility, status_date__gte=date),
            facility=facility
        )
        # set the checkpoint right before the data we are about to process
        save_stock_data_checkpoint(checkpoint,
                                   'supply_point_status',
                                   meta.get('limit') or limit,
                                   meta.get('offset') or offset, date, facility, True)
        for sps in supply_point_statuses:
            try:
                SupplyPointStatus.objects.get(external_id=sps.external_id)
            except SupplyPointStatus.DoesNotExist:
                sps.save()

        if not meta.get('next', False):
            has_next = False
        else:
            next_url = meta['next'].split('?')[1]


def get_supply_point_statuses(domain, endpoint, facilities, checkpoint, date, limit=100, offset=0):
    for facility in facilities:
        sync_supply_point_status(domain, endpoint, facility, checkpoint, date, limit, offset)
        offset = 0


def sync_delivery_group_report(domain, endpoint, facility, checkpoint, date, limit=100, offset=0):
    has_next = True
    next_url = ""
    while has_next:
        meta, delivery_group_reports = endpoint.get_deliverygroupreports(domain, limit=limit, offset=offset,
                                                                         next_url_params=next_url,
                                                                         filters=dict(supply_point=facility,
                                                                                      report_date__gte=date),
                                                                         facility=facility)

        # set the checkpoint right before the data we are about to process
        save_stock_data_checkpoint(checkpoint,
                                   'delivery_group',
                                   meta.get('limit') or limit,
                                   meta.get('offset') or offset,
                                   date, facility, True)
        for dgr in delivery_group_reports:
            try:
                DeliveryGroupReport.objects.get(external_id=dgr.external_id)
            except DeliveryGroupReport.DoesNotExist:
                dgr.save()

        if not meta.get('next', False):
            has_next = False
        else:
            next_url = meta['next'].split('?')[1]


def get_delivery_group_reports(domain, endpoint, facilities, checkpoint, date, limit=100, offset=0):
    for facility in facilities:
        sync_delivery_group_report(domain, endpoint, facility, checkpoint, date, limit, offset)
        offset = 0


# Temporary for staging
@task(queue='background_queue')
def ils_clear_stock_data_task():
    StockTransaction.objects.filter(report__domain='ilsgateway-test-1').delete()
    StockReport.objects.filter(domain='ilsgateway-test-1').delete()
    products = Product.ids_by_domain('ilsgateway-test-1')
    StockState.objects.filter(product_id__in=products).delete()


# @periodic_task(run_every=timedelta(days=1), queue=getattr(settings, 'CELERY_PERIODIC_QUEUE', 'celery'))
@task(queue='background_queue')
def report_run(domain):
    last_successful_run = ReportRun.last_success(domain)
    last_run = ReportRun.last_run(domain)
    start_date = (datetime.min if not last_successful_run else last_successful_run.end)
    end_date = datetime.utcnow()

    running = ReportRun.objects.filter(complete=False, domain=domain)
    if running.count() > 0:
        raise Exception("Warehouse already running, will do nothing...")

    if last_run and last_run.has_error:
        run = last_run
        run.complete = False
        run.save()
    else:
        # start new run
        run = ReportRun.objects.create(start=start_date, end=end_date,
                                       start_run=datetime.utcnow(), domain=domain)
    try:
        run.has_error = True
        populate_report_data(start_date, end_date, domain, run)
        run.has_error = False
    except Exception, e:
        # just in case something funky happened in the DB
        if isinstance(e, DatabaseError):
            try:
                transaction.rollback()
            except:
                pass
        run.has_error = True
        raise
    finally:
        # complete run
        run.end_run = datetime.utcnow()
        run.complete = True
        run.save()
        logging.info("ILSGateway report runner end time: %s" % datetime.now())
