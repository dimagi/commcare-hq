from decimal import Decimal
from casexml.apps.stock.models import StockTransaction


def months_of_stock_remaining(stock, daily_consumption):
    if daily_consumption:
        return stock / Decimal((daily_consumption * 30))
    else:
        return None


def stock_category(stock, daily_consumption, domain):
    if stock is None:
        return 'nodata'
    elif stock == 0:
        return 'stockout'
    elif daily_consumption is None:
        return 'nodata'
    elif daily_consumption == 0:
        return 'overstock'

    months_left = months_of_stock_remaining(stock, daily_consumption)

    stock_levels = domain.commtrack_settings.stock_levels_config

    if months_left is None:
        return 'nodata'
    elif months_left < stock_levels.understock_threshold:
        return 'understock'
    elif months_left > stock_levels.overstock_threshold:
        return 'overstock'
    else:
        return 'adequate'


def state_stock_category(state):
    return stock_category(
        state.stock_on_hand,
        state.get_daily_consumption(),
        state.get_domain()
    )


def get_current_ledger_transactions(case_id):
    """
    Given a case returns a dict of all current ledger data of the following format:
    {
        "section_id": {
             "product_id": StockTransaction,
             "product_id": StockTransaction,
             ...
        },
        ...
    }
    Where you get one stock transaction per product/section which is the last one seen.
    """
    relevant_sections = sorted(StockTransaction.objects.filter(
        case_id=case_id,
    ).values_list('section_id', flat=True).distinct())
    ret = {}
    for section_id in relevant_sections:
        relevant_reports = StockTransaction.objects.filter(
            case_id=case_id,
            section_id=section_id,
        )
        product_ids = relevant_reports.values_list('product_id', flat=True).distinct()
        transactions = {p: StockTransaction.latest(case_id, section_id, p) for p in product_ids}
        ret[section_id] = transactions

    return ret
