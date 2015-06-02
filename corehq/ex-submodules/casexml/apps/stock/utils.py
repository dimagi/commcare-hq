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
    elif stock <= 0:
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
    {
        "section_id": {
             "product_id": StockTransaction,
             "product_id": StockTransaction,
             ...
        },
        ...
    }
    """
    from corehq.apps.commtrack.models import StockState
    results = StockState.objects.filter(case_id=case_id).values_list('case_id', 'section_id', 'product_id')

    ret = {}
    for case_id, section_id, product_id in results:
        sections = ret.setdefault(section_id, {})
        sections[product_id] = StockTransaction.latest(case_id, section_id, product_id)
    return ret


def get_current_ledger_state(case_ids):
    """
    Given a list of cases returns a dict of all current ledger data of the following format:
    {
        "case_id": {
            "section_id": {
                 "product_id": StockState,
                 "product_id": StockState,
                 ...
            },
            ...
        },
        ...
    }
    Where you get one stock transaction per product/section which is the last one seen.
    """
    from corehq.apps.commtrack.models import StockState
    if not case_ids:
        return {}

    states = StockState.objects.filter(
        case_id__in=case_ids
    )
    ret = {case_id: {} for case_id in case_ids}
    for state in states:
        sections = ret[state.case_id].setdefault(state.section_id, {})
        sections[state.product_id] = state

    return ret
