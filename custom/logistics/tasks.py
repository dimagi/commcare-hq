from datetime import datetime
from decimal import Decimal
from functools import partial
import itertools
import celery
from celery.canvas import chain
from django.db import transaction
from casexml.apps.stock.const import TRANSACTION_TYPE_LA
from casexml.apps.stock.models import StockReport, StockTransaction
from casexml.apps.stock.signals import update_stock_state_for_transaction
from corehq.apps.commtrack.models import SupplyPointCase
from corehq.apps.hqcase.dbaccessors import \
    get_supply_point_case_in_domain_by_id
from corehq.apps.locations.models import SQLLocation, Location
from corehq.apps.products.models import SQLProduct
from custom.logistics.commtrack import save_stock_data_checkpoint, synchronization
from custom.logistics.models import StockDataCheckpoint
from dimagi.utils.chunked import chunked
from dimagi.utils.dates import force_to_datetime


@celery.task(queue='background_queue', ignore_result=True)
def stock_data_task(api_object):
    # checkpoint logic
    start_date = datetime.today()
    default_api = api_object.apis[0][0]
    checkpoint, _ = StockDataCheckpoint.objects.get_or_create(domain=api_object.domain, defaults={
        'api': default_api,
        'date': None,
        'limit': 1000,
        'offset': 0,
        'location': None,
        'start_date': start_date
    })

    if not checkpoint.api:
        checkpoint.api = default_api

    if not checkpoint.start_date:
        checkpoint.start_date = start_date
        checkpoint.save()

    if not api_object.all_stock_data:
        facilities = api_object.test_facilities
    else:
        facilities = api_object.get_ids()
    if checkpoint.location:
        external_id = api_object.get_last_processed_location(checkpoint)
        if external_id:
            facilities = list(itertools.dropwhile(lambda x: int(x) != int(external_id), facilities))
            process_facility_task(api_object, facilities[0], start_from=checkpoint.api)
            facilities = facilities[1:]

    if not checkpoint.date or checkpoint.location:
        # use subtasks only during initial migration
        facilities_chunked_list = chunked(facilities, 5)
        for chunk in facilities_chunked_list:
            api_object.process_data(process_facility_task, chunk)
    else:
        offset = checkpoint.offset
        for stock_api in itertools.dropwhile(
            lambda x: x.name != checkpoint.api, api_object.get_stock_apis_objects()
        ):
            stock_api.add_date_filter(checkpoint.date, checkpoint.start_date)
            synchronization(
                stock_api,
                checkpoint,
                checkpoint.date,
                1000,
                offset,
                params={'domain': api_object.domain},
                domain=api_object.domain
            )
            offset = 0

    checkpoint = StockDataCheckpoint.objects.get(domain=api_object.domain)
    save_stock_data_checkpoint(checkpoint, default_api, 1000, 0, checkpoint.start_date, None, False)
    checkpoint.start_date = None
    checkpoint.save()


@celery.task(queue='background_queue')
def process_facility_task(api_object, facility, start_from=None):
    checkpoint = StockDataCheckpoint.objects.get(domain=api_object.domain)
    limit = checkpoint.limit
    offset = checkpoint.offset
    apis = api_object.apis

    if start_from is not None:
        apis = itertools.dropwhile(lambda x: x[0] != checkpoint.api, api_object.apis)

    for idx, (api_name, api_function) in enumerate(apis):
        api_function(
            domain=api_object.domain,
            checkpoint=checkpoint,
            date=checkpoint.date,
            limit=limit,
            offset=offset,
            endpoint=api_object.endpoint,
            facility=facility
        )
        limit = 1000
        offset = 0
    save_stock_data_checkpoint(checkpoint, '', 1000, 0, checkpoint.date, api_object.get_location_id(facility))


@celery.task(queue='background_queue', ignore_result=True)
def resync_web_users(api_object):
    web_users_sync = api_object.apis[5]
    synchronization(web_users_sync, None, None, 100, 0)


@celery.task(ignore_result=True)
def fix_groups_in_location_task(domain):
    locations = Location.by_domain(domain=domain)
    for loc in locations:
        groups = loc.metadata.get('groups', None)
        if groups:
            loc.metadata['group'] = groups[0]
            del loc.metadata['groups']
            loc.save()


@celery.task(ignore_result=True)
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


@celery.task(ignore_result=True)
def add_products_to_loc(api):
    endpoint = api.endpoint
    synchronization(None, endpoint.get_locations, api.location_sync, None, None, 100, 0,
                    filters={"is_active": True})


def sync_stock_transaction(stocktransaction, domain, case=None, bulk=False):
    case = case or get_supply_point_case_in_domain_by_id(domain, stocktransaction.supply_point)
    if not case:
        return
    transactions = []
    section_id = 'stock'
    params = dict(
        form_id='logistics-xform',
        date=force_to_datetime(stocktransaction.date),
        type='balance',
        domain=domain
    )
    try:
        report, _ = StockReport.objects.get_or_create(**params)
    except StockReport.MultipleObjectsReturned:
        # legacy
        report = StockReport.objects.filter(**params)[0]

    sql_product = SQLProduct.objects.get(code=stocktransaction.product, domain=domain)
    if stocktransaction.report_type.lower() == 'stock received':
        transactions.append(StockTransaction(
            case_id=case.get_id,
            product_id=sql_product.product_id,
            sql_product=sql_product,
            section_id=section_id,
            type='receipts',
            stock_on_hand=Decimal(stocktransaction.ending_balance),
            quantity=Decimal(stocktransaction.quantity),
            report=report
        ))
    elif stocktransaction.report_type.lower() == 'stock on hand':
        if stocktransaction.quantity < 0 and bulk:
            transactions.append(StockTransaction(
                case_id=case.get_id,
                product_id=sql_product.product_id,
                sql_product=sql_product,
                section_id=section_id,
                type='consumption',
                stock_on_hand=Decimal(stocktransaction.ending_balance),
                quantity=Decimal(stocktransaction.quantity),
                report=report,
                subtype='inferred'
            ))
        transactions.append(StockTransaction(
            case_id=case.get_id,
            product_id=sql_product.product_id,
            sql_product=sql_product,
            section_id=section_id,
            type='stockonhand',
            stock_on_hand=Decimal(stocktransaction.ending_balance),
            report=report
        ))
    elif stocktransaction.report_type.lower() == 'loss or adjustment':
        transactions.append(StockTransaction(
            case_id=case.get_id,
            product_id=sql_product.product_id,
            sql_product=sql_product,
            section_id=section_id,
            type=TRANSACTION_TYPE_LA,
            stock_on_hand=Decimal(stocktransaction.ending_balance),
            quantity=stocktransaction.quantity,
            report=report
        ))
    if not bulk:
        for tx in transactions:
            tx.save()
    return transactions


def sync_stock_transactions_for_facility(domain, endpoint, facility, checkpoint,
                                         date, limit=1000, offset=0):
    """
    Syncs stock data from StockTransaction objects in ILSGateway to StockTransaction objects in HQ
    """
    has_next = True
    next_url = ""
    section_id = 'stock'
    supply_point = facility
    case = get_supply_point_case_in_domain_by_id(domain, supply_point)
    if not case:
        return
    location_id = case.location_id
    save_stock_data_checkpoint(checkpoint, 'stock_transaction', limit, offset, date, location_id, True)

    products_saved = set()
    while has_next:
        meta, stocktransactions = endpoint.get_stocktransactions(
            next_url_params=next_url,
            limit=limit,
            offset=offset,
            filters={
                'supply_point': supply_point,
                'date__gte': date,
                'date__lte': checkpoint.start_date
            }
        )
        # set the checkpoint right before the data we are about to process
        meta_limit = meta.get('limit') or limit
        meta_offset = meta.get('offset') or offset
        save_stock_data_checkpoint(
            checkpoint, 'stock_transaction', meta_limit, meta_offset, date, location_id, True
        )
        transactions_to_add = []
        with transaction.atomic():
            for stocktransaction in stocktransactions:
                transactions = sync_stock_transaction(stocktransaction, domain, case, bulk=True)
                transactions_to_add.extend(transactions)
                products_saved.update(map(lambda x: x.product_id, transactions))

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
        last_st = StockTransaction.latest(case.get_id, section_id, product)
        update_stock_state_for_transaction(last_st)
