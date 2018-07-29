from __future__ import absolute_import
from __future__ import division
from __future__ import unicode_literals
from decimal import Decimal
from casexml.apps.stock.models import StockTransaction


def months_of_stock_remaining(stock, daily_consumption):
    if daily_consumption:
        return stock / Decimal(daily_consumption * 30)
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


def get_current_ledger_state(case_ids, ensure_form_id=False):
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

    :param ensure_form_id:  Set to True to make sure return StockState
                            have the ``last_modified_form_id`` field populated
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
        if ensure_form_id and not state.last_modified_form_id:
            transaction = StockTransaction.latest(state.case_id, state.section_id, state.product_id)
            if transaction is not None:
                state.last_modified_form_id = transaction.report.form_id
                state.save()
    return ret
