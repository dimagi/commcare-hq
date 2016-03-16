import json
from decimal import Decimal

from dimagi.utils import parsing as dateparse
from datetime import datetime, timedelta
from casexml.apps.stock import const

DEFAULT_CONSUMPTION_FUNCTION = lambda case_id, product_id: None


class ConsumptionConfiguration(object):
    DEFAULT_MIN_PERIODS = 2
    DEFAULT_MIN_WINDOW = 10
    DEFAULT_MAX_WINDOW = 60

    def __init__(self, min_periods=None, min_window=None, max_window=None,
                 default_monthly_consumption_function=None, exclude_invalid_periods=False):
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

        self.default_monthly_consumption_function = _default_if_none(default_monthly_consumption_function,
                                                             DEFAULT_CONSUMPTION_FUNCTION)
        self.exclude_invalid_periods = exclude_invalid_periods

    @classmethod
    def test_config(cls):
        return cls(0, 0, 60)

    def __repr__(self):
        return json.dumps({
            'min_periods': self.min_periods,
            'min_window': self.min_window,
            'max_window': self.max_window,
            'has_default_monthly_consumption_function': bool(self.default_monthly_consumption_function),
            'exclude_invalid_periods': self.exclude_invalid_periods
        }, indent=2)


def from_ts(dt):
    # damn this is ugly
    if isinstance(dt, datetime):
        return dt.replace(tzinfo=None)
    if len(dt) > 20 and dt.endswith('Z'):
        # deal with invalid timestamps (where are these coming from?)
        dt = dt[:-1]
    return dateparse.string_to_datetime(dt).replace(tzinfo=None)

to_ts = dateparse.json_format_datetime


def span_days(start, end):
    span = end - start
    return span.days + span.seconds / 86400.


def compute_daily_consumption(
        domain, case_id, product_id, window_end,
        section_id=const.SECTION_TYPE_STOCK, configuration=None):
    """
    Computes the consumption for a product at a supply point.

    Can optionally pass a section_id, but by default the 'stock'
    value is used for computation.

    Returns None if there is insufficient history.
    """
    from corehq.form_processor.interfaces.dbaccessors import LedgerAccessors

    configuration = configuration or ConsumptionConfiguration()
    window_start = window_end - timedelta(days=configuration.max_window)
    transactions = LedgerAccessors(domain).get_transactions_for_consumption(
        case_id,
        product_id,
        section_id,
        window_start,
        window_end
    )
    return compute_daily_consumption_from_transactions(transactions, window_start, configuration)


def compute_consumption_or_default(
        domain, case_id, product_id, window_end,
        section_id=const.SECTION_TYPE_STOCK, configuration=None):
    """
    Used when it's not important to know if the consumption
    value is real or just a default value
    """
    configuration = configuration or ConsumptionConfiguration()
    daily_consumption = compute_daily_consumption(
        domain,
        case_id,
        product_id,
        window_end,
        section_id,
        configuration
    )

    if daily_consumption:
        return daily_consumption * 30.
    else:
        return compute_default_monthly_consumption(
            case_id,
            product_id,
            configuration,
        )


def compute_default_monthly_consumption(case_id, product_id, configuration):
    return configuration.default_monthly_consumption_function(
        case_id,
        product_id,
    )


def compute_daily_consumption_from_transactions(transactions, window_start, configuration=None):
    configuration = configuration or ConsumptionConfiguration()

    class ConsumptionPeriod(object):
        def __init__(self, tx):
            self.start = from_ts(tx.received_on)
            self.start_soh = tx.normalized_value
            self.end_soh = None
            self.end = None
            self.consumption = 0
            self.receipts = 0

        def add(self, tx):
            self.consumption += tx.normalized_value

        def receipt(self, receipt):
            self.receipts += receipt

        def close_out(self, tx):
            self.end = from_ts(tx.received_on)
            self.end_soh = tx.normalized_value

        def is_valid(self):
            return self.start_soh + Decimal(self.receipts) >= self.end_soh

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
            if tx.is_checkpoint:
                if period:
                    period.close_out(tx)
                    if not configuration.exclude_invalid_periods or period.is_valid():
                        yield period
                period = ConsumptionPeriod(tx)
            elif tx.is_stockout:
                if period:
                    # throw out current period
                    period = None
            elif tx.type == const.TRANSACTION_TYPE_CONSUMPTION:
                # TODO in the future it's possible we'll want to break this out by action_type, in order to track
                # different kinds of consumption: normal vs losses, etc.
                if period:
                    period.add(tx)
            elif configuration.exclude_invalid_periods and tx.type == const.TRANSACTION_TYPE_RECEIPTS:
                if period and period.start:
                    period.receipt(tx.normalized_value)

    periods = list(split_periods(transactions))

    # exclude periods that occur entirely before the averaging window
    periods = filter(lambda period: period.normalized_length, periods)
    total_consumption = sum(period.normalized_consumption for period in periods)
    total_length = sum(period.normalized_length for period in periods)
    # check minimum statistical significance thresholds
    if len(periods) < configuration.min_periods or total_length < configuration.min_window:
        return None

    return total_consumption / float(total_length) if total_length else None
