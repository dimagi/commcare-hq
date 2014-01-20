import collections
import math
from dimagi.utils import parsing as dateparse
from datetime import datetime, timedelta
from casexml.apps.stock import const
from casexml.apps.stock.models import StockTransaction


class ConsumptionConfiguration(object):
    DEFAULT_MIN_PERIODS = 2
    DEFAULT_MIN_WINDOW = 10
    DEFAULT_MAX_WINDOW = 60

    def __init__(self, min_periods=None, min_window=None, max_window=None):
        def _default_if_none(value, default):
            return value if value is not None else default

        # the minimum number of consumption periods to include in a calculation
        # periods are intervals between stock reports
        self.min_periods = _default_if_none(min_periods, self.DEFAULT_MIN_PERIODS)

        # the minimum total time of consumption data to include (in days)
        # consumption should resort to static defaults if less than this
        # amount of data is available
        self.min_window = _default_if_none(min_window, self.DEFAULT_MIN_WINDOW)

        # the maximum time to look backwards for consumption data (in days)
        # data before this period will not be included in the calculation
        self.max_window = _default_if_none(max_window, self.DEFAULT_MAX_WINDOW)

    @classmethod
    def test_config(cls):
        return ConsumptionConfiguration(0, 0, 60)


def from_ts(dt):  # damn this is ugly
    if isinstance(dt, datetime):
        return dt
    if len(dt) > 20 and dt.endswith('Z'): # deal with invalid timestamps (where are these coming from?)
        dt = dt[:-1]
    return dateparse.string_to_datetime(dt).replace(tzinfo=None)
to_ts = dateparse.json_format_datetime


def span_days(start, end):
    span = end - start
    return span.days + span.seconds / 86400.


def compute_consumption(case_id, product_id, window_end, section_id=const.SECTION_TYPE_STOCK,
                        configuration=None):
    configuration = configuration or ConsumptionConfiguration()
    window_start = window_end - timedelta(days=configuration.max_window)
    transactions = get_transactions(case_id, product_id, section_id, window_start, window_end)
    return compute_consumption_from_transactions(transactions, window_start, configuration)


def get_transactions(case_id, product_id, section_id, window_start, window_end):
    """
    Given a case/product pair, get transactions in a format ready for consumption calc
    """
    # todo: get rid of this middle layer once the consumption calc has
    # been updated to deal with the regular transaction objects
    SimpleTransaction = collections.namedtuple('SimpleTransaction', ['action', 'value', 'received_on'])

    def _to_consumption_tx(txn):
        if txn.type == const.TRANSACTION_TYPE_STOCKONHAND:
            value = txn.stock_on_hand
        else:
            assert txn.type in (const.TRANSACTION_TYPE_RECEIPTS, const.TRANSACTION_TYPE_CONSUMPTION)
            value = math.fabs(txn.quantity)
        return SimpleTransaction(
            action=txn.type,
            value=value,
            received_on=txn.report.date,
        )

    # todo: beginning of window date filtering
    db_transactions = StockTransaction.objects.filter(
        case_id=case_id, product_id=product_id,
        report__date__gt=window_start,
        report__date__lte=window_end,
        section_id=section_id,
    ).order_by('report__date', 'pk')

    first = True
    for db_tx in db_transactions:
        # for the very first transaction, include the previous one if there as well
        # to capture the data on the edge of the window
        if first:
            previous = db_tx.get_previous_transaction()
            if previous:
                yield _to_consumption_tx(db_tx)
            first = False

        yield _to_consumption_tx(db_tx)


def compute_consumption_from_transactions(transactions, window_start, configuration=None):
    configuration = configuration or ConsumptionConfiguration()

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
            return float(self.consumption) * self.normalized_length / self.length

    def split_periods(transactions):
        period = None
        for tx in transactions:
            base_action_type = tx.action
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
    if len(periods) < configuration.min_periods or total_length < configuration.min_window:
        return None

    return total_consumption / float(total_length) if total_length else None
