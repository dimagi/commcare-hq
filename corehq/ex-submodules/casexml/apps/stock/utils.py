from decimal import Decimal
from casexml.apps.stock.models import StockTransaction


def months_of_stock_remaining(stock, daily_consumption):
    if daily_consumption:
        return stock / Decimal((daily_consumption * 30))
    else:
        return None


def stock_category(stock, daily_consumption, understock, overstock):
    if stock is None:
        return 'nodata'
    elif stock == 0:
        return 'stockout'
    elif daily_consumption is None:
        return 'nodata'
    elif daily_consumption == 0:
        return 'overstock'

    months_left = months_of_stock_remaining(stock, daily_consumption)
    if months_left is None:
        return 'nodata'
    elif months_left < understock:
        return 'understock'
    elif months_left > overstock:
        return 'overstock'
    else:
        return 'adequate'


def state_stock_category(state):
    if not state.sql_location:
        return 'nodata'
    location_type = state.sql_location.location_type
    return stock_category(
        state.stock_on_hand,
        state.get_daily_consumption(),
        location_type.understock_threshold,
        location_type.overstock_threshold,
    )


def get_current_ledger_transactions(case_id):
    """
    Given a case returns a dict of all current ledger data.
    """
    trans = get_current_ledger_transactions_multi([case_id])
    return trans[case_id]


def get_current_ledger_transactions_multi(case_ids):
    """
    Given a list of cases returns a dict of all current ledger data of the following format:
    {
        "case_id": {
            "section_id": {
                 "product_id": StockTransaction,
                 "product_id": StockTransaction,
                 ...
            },
            ...
        },
        ...
    }
    Where you get one stock transaction per product/section which is the last one seen.
    """
    if not case_ids:
        return {}

    results = StockTransaction.objects.filter(
        case_id__in=case_ids
    ).values_list('case_id', 'section_id', 'product_id').distinct()

    ret = {case_id: {} for case_id in case_ids}
    for case_id, section_id, product_id in results:
        sections = ret[case_id].setdefault(section_id, {})
        sections[product_id] = StockTransaction.latest(case_id, section_id, product_id)

    return ret
