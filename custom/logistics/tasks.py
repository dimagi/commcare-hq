from datetime import datetime
from decimal import Decimal
from functools import partial
import itertools
from couchdbkit import ResourceNotFound
from django.db import transaction
from casexml.apps.stock.models import StockReport, StockTransaction
from corehq.apps.commtrack.models import SupplyPointCase, update_stock_state_for_transaction
from corehq.apps.locations.models import SQLLocation, Location
from corehq.apps.products.models import SQLProduct
from couchforms.models import XFormInstance
from custom.logistics.commtrack import save_stock_data_checkpoint, synchronization
from custom.logistics.models import StockDataCheckpoint
from celery.task.base import task
from custom.logistics.utils import get_supply_point_by_external_id, get_reporting_types
from dimagi.utils.couch.database import iter_docs
from dimagi.utils.dates import force_to_datetime


@task(queue='background_queue')
def stock_data_task(domain, endpoint, apis, config, test_facilities=None):
    # checkpoint logic
    start_date = datetime.today()
    default_api = apis[0][0]

    try:
        checkpoint = StockDataCheckpoint.objects.get(domain=domain)
        api = checkpoint.api
        # legacy
        if api == 'product_stock':
            api = default_api
        date = checkpoint.date
        limit = checkpoint.limit
        offset = checkpoint.offset
        location = checkpoint.location
        if not checkpoint.start_date:
            checkpoint.start_date = start_date
            checkpoint.save()
        else:
            start_date = checkpoint.start_date
    except StockDataCheckpoint.DoesNotExist:
        checkpoint = StockDataCheckpoint()
        checkpoint.domain = domain
        checkpoint.start_date = start_date
        api = default_api
        date = None
        limit = 1000
        offset = 0
        location = None

    if not config.all_stock_data:
        facilities = test_facilities
    else:
        supply_points_ids = SQLLocation.objects.filter(
            domain=domain,
            location_type__in=get_reporting_types(domain)
        ).order_by('created_at').values_list('supply_point_id', flat=True)
        facilities = [doc['external_id'] for doc in iter_docs(SupplyPointCase.get_db(), supply_points_ids)]

    apis_from_checkpoint = itertools.dropwhile(lambda x: x[0] != api, apis)
    facilities_copy = list(facilities)
    if location:
        supply_point = SupplyPointCase.get_by_location_id(domain, location.location_id)
        external_id = supply_point.external_id if supply_point else None
        if external_id:
            facilities = itertools.dropwhile(lambda x: int(x) != int(external_id), facilities)

    for idx, (api_name, api_function) in enumerate(apis_from_checkpoint):
        api_function(
            domain=domain,
            checkpoint=checkpoint,
            date=date,
            limit=limit,
            offset=offset,
            endpoint=endpoint,
            facilities=facilities
        )
        limit = 1000
        offset = 0
        # todo: see if we can avoid modifying the list of facilities in place
        if idx == 0:
            facilities = facilities_copy

    save_stock_data_checkpoint(checkpoint, default_api, 1000, 0, start_date, None, False)
    checkpoint.start_date = None
    checkpoint.save()


@task
def sms_users_fix(api):
    endpoint = api.endpoint
    api.set_default_backend()
    synchronization(None, endpoint.get_smsusers, partial(api.add_language_to_user),
                    None, None, 100, 0)


@task
def fix_groups_in_location_task(domain):
    locations = Location.by_domain(domain=domain)
    for loc in locations:
        groups = loc.metadata.get('groups', None)
        if groups:
            loc.metadata['group'] = groups[0]
            del loc.metadata['groups']
            loc.save()


@task
def locations_fix(domain):
    locations = SQLLocation.objects.filter(domain=domain, location_type__in=['country', 'region', 'district'])
    for loc in locations:
        sp = Location.get(loc.location_id).linked_supply_point()
        if sp:
            sp.external_id = None
            sp.save()
        else:
            fake_location = Location(
                _id=loc.location_id,
                name=loc.name,
                domain=domain
            )
            SupplyPointCase.get_or_create_by_location(fake_location)


@task
def add_products_to_loc(api):
    endpoint = api.endpoint
    synchronization(None, endpoint.get_locations, api.location_sync, None, None, 100, 0,
                    filters={"is_active": True})


def sync_stock_transactions(domain, endpoint, facilities, checkpoint, date, limit=100, offset=0):
    # todo: should figure out whether there's a better thing to be doing than faking this global form
    try:
        xform = XFormInstance.get(docid='ilsgateway-xform')
    except ResourceNotFound:
        xform = XFormInstance(_id='ilsgateway-xform')
        xform.save()
    for facility in facilities:
        sync_stock_transactions_for_facility(domain, endpoint, facility, xform, checkpoint, date, limit, offset)
        offset = 0  # reset offset for each facility, is only set in the context of a checkpoint resume


def sync_stock_transactions_for_facility(domain, endpoint, facility, xform, checkpoint,
                                         date, limit=1000, offset=0):
    """
    Syncs stock data from StockTransaction objects in ILSGateway to StockTransaction objects in HQ
    """
    has_next = True
    next_url = ""
    section_id = 'stock'
    supply_point = facility
    case = get_supply_point_by_external_id(domain, supply_point)
    if not case:
        return

    save_stock_data_checkpoint(checkpoint, 'stock_transaction', limit, offset, date, facility, True)

    products_saved = set()
    while has_next:
        meta, stocktransactions = endpoint.get_stocktransactions(next_url_params=next_url,
                                                                 limit=limit,
                                                                 offset=offset,
                                                                 filters=(dict(supply_point=supply_point,
                                                                               date__gte=date,
                                                                               order_by='date')))

        # set the checkpoint right before the data we are about to process
        meta_limit = meta.get('limit') or limit
        meta_offset = meta.get('offset') or offset
        save_stock_data_checkpoint(checkpoint, 'stock_transaction', meta_limit, meta_offset, date, facility, True)
        transactions_to_add = []
        with transaction.commit_on_success():
            for stocktransaction in stocktransactions:
                params = dict(
                    form_id=xform._id,
                    date=force_to_datetime(stocktransaction.date),
                    type='balance',
                    domain=domain,
                )
                try:
                    report, _ = StockReport.objects.get_or_create(**params)
                except StockReport.MultipleObjectsReturned:
                    # legacy
                    report = StockReport.objects.filter(**params)[0]

                sql_product = SQLProduct.objects.get(code=stocktransaction.product, domain=domain)
                if stocktransaction.quantity != 0:
                    transactions_to_add.append(StockTransaction(
                        case_id=case._id,
                        product_id=sql_product.product_id,
                        sql_product=sql_product,
                        section_id=section_id,
                        type='receipts' if stocktransaction.quantity > 0 else 'consumption',
                        stock_on_hand=Decimal(stocktransaction.ending_balance),
                        quantity=Decimal(stocktransaction.quantity),
                        report=report
                    ))
                transactions_to_add.append(StockTransaction(
                    case_id=case._id,
                    product_id=sql_product.product_id,
                    sql_product=sql_product,
                    section_id=section_id,
                    type='stockonhand',
                    stock_on_hand=Decimal(stocktransaction.ending_balance),
                    report=report
                ))
                products_saved.add(sql_product.product_id)

        if transactions_to_add:
            # Doesn't send signal
            StockTransaction.objects.bulk_create(transactions_to_add)

        if not meta.get('next', False):
            has_next = False
        else:
            next_url = meta['next'].split('?')[1]

    for product in products_saved:
        # if we saved anything rebuild the stock state object by firing the signal
        # on the last transaction for each product
        last_st = StockTransaction.latest(case._id, section_id, product)
        update_stock_state_for_transaction(last_st)
