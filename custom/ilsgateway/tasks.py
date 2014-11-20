from datetime import datetime
from decimal import Decimal
import logging

from celery.task import task
from couchdbkit.exceptions import ResourceNotFound
from django.db import transaction
from psycopg2._psycopg import DatabaseError

from casexml.apps.stock.models import StockReport, StockTransaction
from corehq.apps.commtrack.models import StockState, SupplyPointCase
from corehq.apps.products.models import Product, SQLProduct
from corehq.apps.consumption.const import DAYS_IN_MONTH
from couchforms.models import XFormInstance
from custom.ilsgateway.api import Location
from custom.ilsgateway.commtrack import bootstrap_domain as ils_bootstrap_domain, sync_ilsgateway_location, commtrack_settings_sync,\
    sync_ilsgateway_product
from custom.ilsgateway.models import ILSGatewayConfig, SupplyPointStatus, DeliveryGroupReport, ReportRun
from custom.ilsgateway.tanzania.api import TanzaniaEndpoint
from custom.ilsgateway.tanzania.warehouse_updater import populate_report_data
from dimagi.utils.dates import force_to_datetime





# @periodic_task(run_every=timedelta(days=1), queue=getattr(settings, 'CELERY_PERIODIC_QUEUE', 'celery'))
def migration_task():
    configs = ILSGatewayConfig.get_all_configs()
    for config in configs:
        if config.enabled:
            ils_bootstrap_domain(config)


@task
def ils_bootstrap_domain_task(domain):
    ils_config = ILSGatewayConfig.for_domain(domain)
    return ils_bootstrap_domain(ils_config)

# District Moshi-Rural
ILS_FACILITIES = [906, 907, 908, 909]


def get_locations(domain, endpoint, facilities):
    for facility in facilities:
        location = endpoint.get_location(facility, params=dict(with_historical_groups=1))
        sync_ilsgateway_location(domain, endpoint, Location(location))


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
                else:
                    stock_state.daily_consumption = None
                stock_state.save()

            if not meta.get('next', False):
                has_next = False
            else:
                next_url = meta['next'].split('?')[1]


def get_stock_transaction(domain, endpoint, facilities):
    # Faking xform
    try:
        xform = XFormInstance.get(docid='ilsgateway-xform')
    except ResourceNotFound:
        xform = XFormInstance(_id='ilsgateway-xform')
        xform.save()

    for facility in facilities:
        has_next = True
        next_url = ""

        while has_next:
            meta, stocktransactions = endpoint.get_stocktransactions(next_url_params=next_url,
                                                                     filters=(dict(supply_point=facility,
                                                                                   order_by='date')))
            for stocktransaction in stocktransactions:
                case = SupplyPointCase.view('hqcase/by_domain_external_id',
                                            key=[domain, str(stocktransaction.supply_point)],
                                            reduce=False,
                                            include_docs=True,
                                            limit=1).first()
                product = Product.get_by_code(domain, stocktransaction.product)
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


def get_supply_point_statuses(domain, endpoint, facilities):
    for facility in facilities:
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


def get_delivery_group_reports(domain, endpoint, facilities):
    for facility in facilities:
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
def ils_stock_data_task(domain):
    ilsgateway_config = ILSGatewayConfig.for_domain(domain)
    domain = ilsgateway_config.domain
    endpoint = TanzaniaEndpoint.from_config(ilsgateway_config)
    commtrack_settings_sync(domain)
    for product in endpoint.get_products():
        sync_ilsgateway_product(domain, product)
    get_locations(domain, endpoint, ILS_FACILITIES)
    get_product_stock(domain, endpoint, ILS_FACILITIES)
    get_stock_transaction(domain, endpoint, ILS_FACILITIES)
    get_supply_point_statuses(domain, endpoint, ILS_FACILITIES)
    get_delivery_group_reports(domain, endpoint, ILS_FACILITIES)

# Temporary for staging
@task
def ils_clear_stock_data_task():
    StockTransaction.objects.filter(report__domain='ilsgateway-test-1').delete()
    StockReport.objects.filter(domain='ilsgateway-test-1').delete()
    products = Product.ids_by_domain('ilsgateway-test-1')
    StockState.objects.filter(product_id__in=products).delete()

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
