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
from custom.ilsgateway import TEST
from custom.logistics.commtrack import save_stock_data_checkpoint, synchronization
from custom.logistics.models import StockDataCheckpoint
from celery.task.base import task
from custom.logistics.utils import get_supply_point_by_external_id
from dimagi.utils.dates import force_to_datetime


def get_or_create_checkpoint(domain, default_api):
    try:
        checkpoint = StockDataCheckpoint.objects.get(domain=domain)
        if not checkpoint.start_date:
            checkpoint.start_date = datetime.today()
            checkpoint.save()
        return checkpoint, False
    except StockDataCheckpoint.DoesNotExist:
        return StockDataCheckpoint(
            domain=domain,
            date=None,
            start_date=datetime.today(),
            api=default_api,
            limit=100,
            offset=0,
            location=None,
        ), True


@task
def stock_data_task(domain, endpoint, apis, test_facilities=None):
    if TEST:
        facilities = test_facilities
    else:
        facilities = SQLLocation.objects.filter(
            domain=domain,
            location_type__iexact='FACILITY'
        ).order_by('created_at').values_list('external_id', flat=True)

    facilities_copy = list(facilities)

    default_api = apis[0][0]
    # checkpoint logic
    checkpoint, created = get_or_create_checkpoint(domain, default_api)
    if not created:
        # filter apis, location, etc. form checkpoint data
        apis = itertools.dropwhile(lambda x: x[0] != checkpoint.api, apis)
        if checkpoint.location:
            supply_point = SupplyPointCase.view(
                'commtrack/supply_point_by_loc',
                key=[checkpoint.location.domain, checkpoint.location.location_id],
                include_docs=True,
                classes={'CommCareCase': SupplyPointCase},
            ).one()
            external_id = supply_point.external_id if supply_point else None
            if external_id:
                facilities = itertools.dropwhile(lambda x: int(x) != int(external_id), facilities)

    limit = checkpoint.limit
    offset = checkpoint.offset
    for idx, (api_name, api_function) in enumerate(apis):
        api_function(
            domain=domain,
            checkpoint=checkpoint,
            date=checkpoint.date,
            limit=limit,
            offset=offset,
            endpoint=endpoint,
            facilities=facilities
        )
        limit = 100
        offset = 0
        # todo: see if we can avoid modifying the list of facilities in place
        if idx == 0:
            facilities = facilities_copy
    save_stock_data_checkpoint(checkpoint, default_api, 100, 0, None, None)


@task
def sms_users_fix(api):
    endpoint = api.endpoint
    api.set_default_backend()
    synchronization(None, endpoint.get_smsusers, partial(api.add_language_to_user),
                    None, None, 100, 0)


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
                           date, limit=100, offset=0):
    """
    Syncs stock data from StockTransaction objects in ILSGateway to StockTransaction objects in HQ
    """
    has_next = True
    next_url = ""
    section_id = 'stock'
    supply_point = facility
    case = get_supply_point_by_external_id(domain, supply_point)
    if case:
        products_saved = set()
        while has_next:
            meta, stocktransactions = endpoint.get_stocktransactions(next_url_params=next_url,
                                                                     limit=limit,
                                                                     offset=offset,
                                                                     filters=(dict(supply_point=supply_point,
                                                                                   date__gte=date,
                                                                                   order_by='date')))

            # set the checkpoint right before the data we are about to process
            save_stock_data_checkpoint(checkpoint,
                                       'stock_transaction',
                                       meta.get('limit') or limit,
                                       meta.get('offset') or offset,
                                       date, facility, True)
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
                    try:
                        sql_product = SQLProduct.objects.get(code=stocktransaction.product, domain=domain)
                    except SQLProduct.DoesNotExist:
                        # todo: kkrampa what's the deal with this logic? this should never be true
                        continue

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
