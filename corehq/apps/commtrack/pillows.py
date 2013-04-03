from pillowtop.listener import BasicPillow
from couchforms.models import XFormInstance
from corehq.apps.commtrack.models import StockTransaction
import collections
from dimagi.utils import parsing as dateparse
from datetime import datetime, timedelta

from_ts = lambda dt: dateparse.string_to_datetime(dt).replace(tzinfo=None)
to_ts = dateparse.json_format_datetime

class ConsumptionRatePillow(BasicPillow):
    document_class = XFormInstance
    couch_filter = 'commtrack/stock_reports'

    def change_transform(self, doc_dict):
        txs = doc_dict['form']['transaction']
        if not isinstance(txs, collections.Sequence):
            txs = [txs]
        touched_products = set(tx['product_entry'] for tx in txs)

        for case_id in touched_products:
            print compute_consumption(case_id, from_ts(doc_dict['received_on']))

CONSUMPTION_WINDOW = 60 # days
WINDOW_OVERSHOOT = 15 # days

MIN_WINDOW = 10 # days
MIN_PERIODS = 2 # is this a good filter? differs a bit from malawi

def span_days(start, end):
    span = end - start
    return span.days + span.seconds / 86400.

def compute_consumption(product_case, window_end):
    window_start = window_end - timedelta(days=CONSUMPTION_WINDOW)
    overshoot_start = window_start - timedelta(days=WINDOW_OVERSHOOT)

    transactions = list(StockTransaction.by_product(product_case, to_ts(overshoot_start), to_ts(window_end)))
    transactions.sort(key=lambda tx: (tx.received_on, tx.processing_order))

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
            base_action_type = tx.action #FIXME
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
                if period:
                    period.add(tx)
    periods = list(split_periods(transactions))

    # exclude periods that occur entirely before the averaging window
    periods = filter(lambda period: period.normalized_length, periods)
    total_consumption = sum(period.normalized_consumption for period in periods) 
    total_length = sum(period.normalized_length for period in periods)

    # check minimum statistical significance thresholds
    if len(periods) < MIN_PERIODS or total_length < MIN_DAYS:
        return None

    return total_consumption / float(total_length)

