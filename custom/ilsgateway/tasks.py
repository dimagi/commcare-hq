from datetime import datetime
from decimal import Decimal
import logging
from celery.task import task
from couchdbkit.exceptions import ResourceNotFound
from django.db import transaction
from psycopg2._psycopg import DatabaseError
from casexml.apps.stock.models import StockReport, StockTransaction
from corehq.apps.commtrack.models import StockState, SupplyPointCase, Product, SQLProduct
from couchforms.models import XFormInstance
from custom.ilsgateway.api import ILSGatewayEndpoint, Location
from custom.ilsgateway.commtrack import bootstrap_domain, sync_ilsgateway_location, commtrack_settings_sync,\
    sync_ilsgateway_product

from custom.ilsgateway.models import ILSGatewayConfig, SupplyPointStatus, DeliveryGroupReport, ReportRun
from custom.ilsgateway.run_reports import populate_report_data

from dimagi.utils.dates import force_to_datetime


# @periodic_task(run_every=timedelta(days=1), queue=getattr(settings, 'CELERY_PERIODIC_QUEUE', 'celery'))
def migration_task():
    configs = ILSGatewayConfig.get_all_configs()
    for config in configs:
        if config.enabled:
            bootstrap_domain(config)


@task
def bootstrap_domain_task(domain):
    ilsgateway_config = ILSGatewayConfig.for_domain(domain)
    return bootstrap_domain(ilsgateway_config)

# District Moshi-Rural
FACILITIES = [948, 998, 974, 1116, 971, 1122, 921, 658, 995, 1057,
              652, 765, 1010, 657, 1173, 1037, 965, 749, 1171, 980,
              1180, 1033, 975, 1056, 970, 742, 985, 2194, 935, 1128,
              1172, 773, 916, 1194, 4862, 1003, 994, 1034, 1113, 1167,
              949, 987, 986, 960, 1046, 942, 972, 21, 952, 930, 1170, 1067,
              1006, 752, 747, 1176, 746, 755, 1102, 924, 744, 1109, 760, 922,
              945, 988, 927, 1045, 1060, 938, 1041, 1101, 1107, 939, 910, 934,
              929, 1111, 1174, 1044, 1008, 914, 1040, 1035, 1126, 1203, 912, 990,
              908, 654, 1051, 1110, 983, 771, 1068, 756, 4807, 973, 1013, 911, 1048,
              1196, 917, 1127, 963, 1032, 1164, 951, 918, 999, 923, 1049, 1000, 1165,
              915, 1036, 1121, 758, 1054, 1042, 4861, 1007, 1053, 954, 761, 1002, 748,
              919, 976, 1177, 1179, 1001, 743, 762, 741, 959, 1119, 772, 941, 956, 964,
              1014, 953, 754, 1202, 1166, 977, 757, 961, 759, 997, 947, 1112, 978, 1124,
              768, 937, 1195, 913, 906, 1043, 1178, 992, 1038, 957, 1106, 767, 979, 1012,
              926, 1120, 933, 1066, 1105, 943, 1047, 1063, 1004, 958, 751, 763, 1011, 936,
              1114, 932, 984, 656, 653, 946, 1058, 931, 770, 1108, 909, 1118, 1062, 745, 1065,
              955, 1052, 753, 944, 1061, 1069, 1104, 996, 4860, 950, 993, 1064, 1175, 1059, 1050,
              968, 928, 989, 967, 966, 750, 981, 1055, 766, 1123, 1039, 1103, 655, 1125, 774, 991,
              1117, 920, 769, 1005, 1009, 925, 1115, 907]


def get_locations(domain, endpoint):
    for facility in FACILITIES:
        location = endpoint.get_location(facility)
        sync_ilsgateway_location(domain, endpoint, Location.from_json(location))


def get_product_stock(domain, endpoint):
    for facility in FACILITIES:
        has_next = True
        next_url = ""

        while has_next:
            meta, product_stocks = endpoint.get_productstocks(next_url_params=next_url,
                                                              filters=dict(supply_point=facility))
            for product_stock in product_stocks:
                case = SupplyPointCase.view('hqcase/by_domain_external_id',
                                            key=[domain, str(product_stock.supply_point_id)],
                                            reduce=False,
                                            include_docs=True,
                                            limit=1).first()
                product = Product.get_by_code(domain, product_stock.product_code)
                try:
                    StockState.objects.get(section_id='stock', case_id=case._id, product_id=product._id)
                except StockState.DoesNotExist:
                    StockState.objects.create(section_id='stock',
                                              case_id=case._id,
                                              product_id=product._id,
                                              stock_on_hand=product_stock.quantity or 0,
                                              daily_consumption=product_stock.auto_monthly_consumption or 0,
                                              last_modified_date=product_stock.last_modified,
                                              sql_product=SQLProduct.objects.get(product_id=product._id))
            if not meta.get('next', False):
                has_next = False
            else:
                next_url = meta['next'].split('?')[1]


def get_stock_transaction(domain, endpoint):
    # Faking xform
    try:
        xform = XFormInstance.get(docid='ilsgateway-xform')
    except ResourceNotFound:
        xform = XFormInstance(_id='ilsgateway-xform')
        xform.save()

    for facility in FACILITIES:
        has_next = True
        next_url = ""

        while has_next:
            meta, stocktransactions = endpoint.get_stocktransactions(next_url_params=next_url,
                                                                     filters=(dict(supply_point=facility,
                                                                                   order_by='date')))
            for stocktransaction in stocktransactions:
                case = SupplyPointCase.view('hqcase/by_domain_external_id',
                                            key=[domain, str(stocktransaction.supply_point_id)],
                                            reduce=False,
                                            include_docs=True,
                                            limit=1).first()
                product = Product.get_by_code(domain, stocktransaction.product_code)
                try:
                    StockTransaction.objects.get(case_id=case._id,
                                                 product_id=product._id,
                                                 report__date=force_to_datetime(stocktransaction.date),
                                                 stock_on_hand=Decimal(stocktransaction.ending_balance),
                                                 type='stockonhand', report__domain=domain)
                except StockTransaction.DoesNotExist:
                    r = StockReport.objects.create(form_id=xform._id,
                                                   date=force_to_datetime(stocktransaction.date),
                                                   type='balance',
                                                   domain=domain)
                    StockTransaction.objects.create(report=r,
                                                    section_id='stock',
                                                    case_id=case._id,
                                                    product_id=product._id,
                                                    type='stockonhand',
                                                    stock_on_hand=Decimal(stocktransaction.ending_balance))
            if not meta.get('next', False):
                has_next = False
            else:
                next_url = meta['next'].split('?')[1]


def get_supply_point_statuses(domain, endpoint):
    for facility in FACILITIES:
        has_next = True
        next_url = ""

        while has_next:
            meta, supply_point_statuses = endpoint.get_supplypointstatuses(domain,
                                                                           next_url_params=next_url,
                                                                           filters=dict(supply_point=facility),
                                                                           facility=facility)
            for sps in supply_point_statuses:
                try:
                    SupplyPointStatus.objects.get(external_id=sps.external_id)
                except SupplyPointStatus.DoesNotExist:
                    sps.save()

            if not meta.get('next', False):
                has_next = False
            else:
                next_url = meta['next'].split('?')[1]


def get_delivery_group_reports(domain, endpoint):
    for facility in FACILITIES:
        has_next = True
        next_url = ""
        while has_next:
            meta, delivery_group_reports = endpoint.get_deliverygroupreports(domain,
                                                                             next_url_params=next_url,
                                                                             filters=dict(supply_point=facility),
                                                                             facility=facility)
            for dgr in delivery_group_reports:
                try:
                    DeliveryGroupReport.objects.get(external_id=dgr.external_id)
                except DeliveryGroupReport.DoesNotExist:
                    dgr.save()

            if not meta.get('next', False):
                has_next = False
            else:
                next_url = meta['next'].split('?')[1]


@task
def stock_data_task(domain):
    ilsgateway_config = ILSGatewayConfig.for_domain(domain)
    domain = ilsgateway_config.domain
    endpoint = ILSGatewayEndpoint.from_config(ilsgateway_config)
    commtrack_settings_sync(domain)
    for product in endpoint.get_products():
        sync_ilsgateway_product(domain, product)
    get_locations(domain, endpoint)
    get_product_stock(domain, endpoint)
    get_stock_transaction(domain, endpoint)
    get_supply_point_statuses(domain, endpoint)
    get_delivery_group_reports(domain, endpoint)


# @periodic_task(run_every=timedelta(days=1), queue=getattr(settings, 'CELERY_PERIODIC_QUEUE', 'celery'))
@task
def report_run(domain):
    last_run = ReportRun.last_success(domain)
    start_date = (datetime.min if not last_run else last_run.end)
    end_date = datetime.utcnow()

    running = ReportRun.objects.filter(complete=False, domain=domain)
    if running.count() > 0:
        raise Exception("Warehouse already running, will do nothing...")

    # start new run
    new_run = ReportRun.objects.create(start=start_date, end=end_date,
                                       start_run=datetime.utcnow(), domain=domain)
    try:
        populate_report_data(start_date, end_date, domain)
    except Exception, e:
        # just in case something funky happened in the DB
        if isinstance(e, DatabaseError):
            try:
                transaction.rollback()
            except:
                pass
        new_run.has_error = True
        raise
    finally:
        # complete run
        new_run.end_run = datetime.utcnow()
        new_run.complete = True
        new_run.save()
        logging.info("ILSGateway report runner end time: %s" % datetime.now())
