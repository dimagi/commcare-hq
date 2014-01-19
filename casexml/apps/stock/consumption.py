import collections
from dimagi.utils import parsing as dateparse
from datetime import datetime
from casexml.apps.stock import const
from casexml.apps.stock.models import StockTransaction


def from_ts(dt): #damn this is ugly
    if isinstance(dt, datetime):
        return dt
    if len(dt) > 20 and dt.endswith('Z'): # deal with invalid timestamps (where are these coming from?)
        dt = dt[:-1]
    return dateparse.string_to_datetime(dt).replace(tzinfo=None)
to_ts = dateparse.json_format_datetime


def span_days(start, end):
    span = end - start
    return span.days + span.seconds / 86400.


def expand_transactions(case_id, product_id, window_end):
    """
    Given a case/product pair, expand transactions by adding the inferred ones
    """
    # todo: get rid of this middle layer once the consumption calc has
    # been updated to deal with the regular transaction objects
    SimpleTransaction = collections.namedtuple('SimpleTransaction', ['action', 'value', 'received_on'])
    def _soh_to_consumption_tx(soh_tx):
        assert soh_tx.report.type == const.TRANSACTION_TYPE_BALANCE
        assert soh_tx.quantity == soh_tx.stock_on_hand
        return SimpleTransaction(
            action='stockonhand',
            value=soh_tx.stock_on_hand,
            received_on=soh_tx.report.date,
        )

    # todo: beginning of window date filtering
    db_transactions = StockTransaction.objects.filter(
        case_id=case_id, product_id=product_id, report__date__lte=window_end
    ).order_by('report__date')
    for db_tx in db_transactions:
        yield _soh_to_consumption_tx(db_tx)

def compute_consumption_from_transactions(transactions, window_start, get_base_action, params=None):
    params = params or {}

    class ConsumptionPeriod(object):
        def __init__(self, tx):
            self.start = from_ts(tx.received_on)
            self.end = None
            self.consumption = 0

        def add(self, tx):
            self.consumption += tx.value

        def close_out(self, tx):
            self.end = from_ts(tx.received_on)

        @property
        def length(self):
            return span_days(self.start, self.end)

        @property
        def normalized_length(self):
            return span_days(max(self.start, window_start), max(self.end, window_start))

        @property
        def normalized_consumption(self):
            return self.consumption * self.normalized_length / self.length

    def split_periods(transactions):
        period = None
        for tx in transactions:
            base_action_type = get_base_action(tx.action)
            is_stockout = (
                base_action_type == 'stockout' or
                (base_action_type == 'stockonhand' and tx.value == 0) or
                (base_action_type == 'stockedoutfor' and tx.value > 0)
            )
            is_checkpoint = (base_action_type == 'stockonhand' and not is_stockout)

            if is_checkpoint:
                if period:
                    period.close_out(tx)
                    yield period
                period = ConsumptionPeriod(tx)
            elif is_stockout:
                if period:
                    # throw out current period
                    period = None
            elif base_action_type == 'consumption':
                # TODO in the future it's possible we'll want to break this out by action_type, in order to track
                # different kinds of consumption: normal vs losses, etc.
                if period:
                    period.add(tx)

    periods = list(split_periods(transactions))

    # exclude periods that occur entirely before the averaging window
    periods = filter(lambda period: period.normalized_length, periods)
    total_consumption = sum(period.normalized_consumption for period in periods)
    total_length = sum(period.normalized_length for period in periods)

    # check minimum statistical significance thresholds
    if len(periods) < params.get('min_periods', 0) or total_length < params.get('min_window', 0):
        return None

    return total_consumption / float(total_length) if total_length else None
