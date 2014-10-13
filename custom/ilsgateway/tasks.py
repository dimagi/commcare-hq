from decimal import Decimal
from celery.task import task, periodic_task
from couchdbkit.exceptions import ResourceNotFound
from casexml.apps.stock.models import StockReport, StockTransaction
from corehq.apps.commtrack.models import StockState, SupplyPointCase, Product, SQLProduct
from couchforms.models import XFormInstance
from custom.ilsgateway.api import ILSGatewayEndpoint, Location
from custom.ilsgateway.commtrack import bootstrap_domain, sync_ilsgateway_location


#@periodic_task(run_every=timedelta(days=1), queue=getattr(settings, 'CELERY_PERIODIC_QUEUE', 'celery'))
from custom.ilsgateway.models import ILSGatewayConfig, SupplyPointStatus
from dimagi.utils.dates import force_to_datetime


def migration_task():
    configs = ILSGatewayConfig.get_all_configs()
    for config in configs:
        if config.enabled:
            bootstrap_domain(config)


@task
def bootstrap_domain_task(domain):
    ilsgateway_config = ILSGatewayConfig.for_domain(domain)
    return bootstrap_domain(ilsgateway_config)

# Region Arumeru
FACILITIES = [660, 661, 663, 664, 665, 667, 668, 669, 676, 677, 678,
              679, 680, 681, 682, 684, 688, 690, 691, 692, 693,
              694, 695, 701, 702, 703, 705, 706, 707, 1182, 1183]


@task
def get_locations_task(domain):
    ilsgateway_config = ILSGatewayConfig.for_domain(domain)
    domain = ilsgateway_config.domain
    endpoint = ILSGatewayEndpoint.from_config(ilsgateway_config)
    for facility in FACILITIES:
        location = endpoint.get_location(facility)
        sync_ilsgateway_location(domain, endpoint, Location.from_json(location))


@task
def product_stock_task(domain):
    ilsgateway_config = ILSGatewayConfig.for_domain(domain)
    domain = ilsgateway_config.domain
    endpoint = ILSGatewayEndpoint.from_config(ilsgateway_config)
    for facility in FACILITIES:
        product_stocks = endpoint.get_productstocks(filters=dict(supply_point=facility))[1]
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




@task
def stock_transaction_task(domain):
    ilsgateway_config = ILSGatewayConfig.for_domain(domain)
    domain = ilsgateway_config.domain
    endpoint = ILSGatewayEndpoint.from_config(ilsgateway_config)

    # Faking xform
    try:
        xform = XFormInstance.get(docid='ilsgateway-xform')
    except ResourceNotFound:
        xform = XFormInstance(_id='ilsgateway-xform')
        xform.save()

    for facility in FACILITIES:
        stocktransactions = endpoint.get_stocktransactions(filters=(dict(supply_point=facility)))[1]
        for stocktransaction in stocktransactions:
            case = SupplyPointCase.view('hqcase/by_domain_external_id',
                                        key=[domain, str(stocktransaction.supply_point_id)],
                                        reduce=False,
                                        include_docs=True,
                                        limit=1).first()
            product = Product.get_by_code(domain, stocktransaction.product_code)
            try:
                StockTransaction.objects.get(case_id=case._id,
                                             product_id=product._id, report__date=force_to_datetime(stocktransaction.date),
                                             stock_on_hand=Decimal(stocktransaction.ending_balance),
                                             type='stockonhand', report__domain=domain)
            except StockTransaction.DoesNotExist:
                r = StockReport.objects.create(form_id=xform._id, date=force_to_datetime(stocktransaction.date),
                                               type='balance', domain=domain)
                StockTransaction.objects.create(report=r, section_id='stock', case_id=case._id, product_id=product._id,
                                                type='stockonhand', stock_on_hand=Decimal(stocktransaction.ending_balance))


@task
def supply_point_statuses_task(domain):
    ilsgateway_config = ILSGatewayConfig.for_domain(domain)
    domain = ilsgateway_config.domain
    endpoint = ILSGatewayEndpoint.from_config(ilsgateway_config)
    for facility in FACILITIES:
        supplypointstatuses = endpoint.get_supplypointstatuses(domain, filters=dict(supply_point=facility))[1]
        for sps in supplypointstatuses:
            sps.save()


