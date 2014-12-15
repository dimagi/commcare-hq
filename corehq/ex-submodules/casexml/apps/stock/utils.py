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

    relevant_transactions = StockTransaction.objects.raw(
        """
        SELECT MAX(stx.id) AS id FROM
        (
            SELECT case_id, product_id, section_id, MAX(sr.date) AS date
            FROM stock_stocktransaction st JOIN stock_stockreport sr ON st.report_id = sr.id
            WHERE case_id IN %s
            GROUP BY case_id, section_id, product_id
        ) AS x INNER JOIN stock_stocktransaction AS stx ON
            stx.case_id = x.case_id
            AND stx.product_id = x.product_id
            AND stx.section_id = x.section_id
        JOIN stock_stockreport str ON
            str.date = x.date
            AND stx.report_id = str.id
        GROUP BY stx.case_id, stx.product_id, stx.section_id, str.date;
        """,
        [tuple(case_ids)]
    )

    transaction_ids = [tx.id for tx in relevant_transactions]
    results = StockTransaction.objects.filter(id__in=transaction_ids).select_related()
    ret = {case_id: {} for case_id in case_ids}
    for txn in results:
        sections = ret[txn.case_id].setdefault(txn.section_id, {})
        sections[txn.product_id] = txn
    return ret
