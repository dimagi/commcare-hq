from datetime import datetime
from decimal import Decimal
from celery import group
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

from custom.ilsgateway.models import ILSGatewayConfig, SupplyPointStatus, DeliveryGroupReport, GroupSummary, \
    ProductAvailabilityData, ReportRun
from custom.ilsgateway.run_reports import populate_report_data

from dimagi.utils.dates import force_to_datetime


#@periodic_task(run_every=timedelta(days=1), queue=getattr(settings, 'CELERY_PERIODIC_QUEUE', 'celery'))
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
FACILITIES = [906, 907, 908, 909, 910, 911, 912, 913, 914, 915, 916,
              917, 918, 919, 920, 921, 922, 923, 924, 925, 926, 927,
              928, 929, 930, 931, 932, 933, 934, 935, 936, 937, 938,
              939, 941, 942, 943, 944, 946, 947, 948, 949, 950, 951,
              952, 953, 954, 955, 4860, 654]


def get_locations(domain, endpoint):
    for facility in FACILITIES:
        location = endpoint.get_location(facility)
        sync_ilsgateway_location(domain, endpoint, Location.from_json(location))


@task
def product_stock_task(domain, endpoint):
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
                next_url = meta['next'].split('?')[1] if meta['next'] else None


@task
def stock_transaction_task(domain, endpoint):
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
                next_url = meta['next'].split('?')[1] if meta['next'] else None


@task
def supply_point_statuses_task(domain, endpoint):
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
                next_url = meta['next'].split('?')[1] if meta['next'] else None


@task
def delivery_group_reports_task(domain, endpoint):
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
                next_url = meta['next'].split('?')[1] if meta['next'] else None


@task
def stock_data_task(domain):
    ilsgateway_config = ILSGatewayConfig.for_domain(domain)
    domain = ilsgateway_config.domain
    endpoint = ILSGatewayEndpoint.from_config(ilsgateway_config)
    commtrack_settings_sync(domain)
    for product in endpoint.get_products():
        sync_ilsgateway_product(domain, product)
    get_locations(domain, endpoint)
    product_stock_task.delay(domain, endpoint)
    stock_transaction_task.delay(domain, endpoint)
    supply_point_statuses_task.delay(domain, endpoint)
    delivery_group_reports_task.delay(domain, endpoint)


#@periodic_task(run_every=timedelta(days=1), queue=getattr(settings, 'CELERY_PERIODIC_QUEUE', 'celery'))
@task
def report_run(domain):
    last_run = ReportRun.last_success()
    start_date = (datetime.min if not last_run else last_run.end)
    end_date = datetime.utcnow()

    running = ReportRun.objects.filter(complete=False)
    if running.count() > 0:
        raise Exception("Warehouse already running, will do nothing...")

    # start new run
    new_run = ReportRun.objects.create(start=start_date, end=end_date,
                                       start_run=datetime.utcnow())
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