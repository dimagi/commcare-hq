import logging
from couchdbkit import ResourceNotFound
from pillowtop.listener import BasicPillow
from couchforms.models import XFormInstance
from corehq.apps.commtrack.models import StockTransaction
import collections
from dimagi.utils import parsing as dateparse
from datetime import datetime, timedelta
from corehq.apps.domain.models import Domain
from casexml.apps.case.models import CommCareCase
from corehq.apps.commtrack.models import ACTION_TYPES

pillow_logging = logging.getLogger("pillowtop")

def from_ts(dt): #damn this is ugly
    if isinstance(dt, datetime):
        return dt
    if len(dt) > 20 and dt.endswith('Z'): # deal with invalid timestamps (where are these coming from?)
        dt = dt[:-1]
    return dateparse.string_to_datetime(dt).replace(tzinfo=None)
to_ts = dateparse.json_format_datetime

class ConsumptionRatePillow(BasicPillow):
    document_class = XFormInstance
    couch_filter = 'commtrack/stock_reports'

    def change_transform(self, doc_dict):
        txs = doc_dict['form'].get('transaction', [])
        if not isinstance(txs, collections.Sequence):
            txs = [txs]
        touched_products = set(tx['product_entry'] for tx in txs)

        action_defs = Domain.get_by_name(doc_dict['domain']).commtrack_settings.all_actions_by_name
        def get_base_action(action):
            try:
                return action_defs[action].action_type
            except KeyError:
                # this arises because inferred transactions might not map cleanly to user-defined action types
                # need to find a more understandable solution
                if action in ACTION_TYPES:
                    return action
                else:
                    raise

        for case_id in touched_products:
            rate = compute_consumption(case_id, from_ts(doc_dict['received_on']), get_base_action)

            try:
                case = CommCareCase.get(case_id)
                set_computed(case, 'consumption_rate', rate)
                case.save()
            except ResourceNotFound:
                # maybe the case was deleted. for now we don't care about this
                pillow_logging.info('skipping commtrack update for deleted case %s' % case_id)

# TODO: biyeun might have better framework code for doing this
def set_computed(case, key, val):
    NAMESPACE = 'commtrack'
    if not NAMESPACE in case.computed_:
        case.computed_[NAMESPACE] = {}
    case.computed_[NAMESPACE][key] = val

# TODO make into domain settings
CONSUMPTION_WINDOW = 60 # days
WINDOW_OVERSHOOT = 15 # days
MIN_WINDOW = 10 # days
MIN_PERIODS = 2 # is this a good filter? differs a bit from malawi

def span_days(start, end):
    span = end - start
    return span.days + span.seconds / 86400.

def compute_consumption(product_case, window_end, get_base_action):
    window_start = window_end - timedelta(days=CONSUMPTION_WINDOW)
    overshoot_start = window_start - timedelta(days=WINDOW_OVERSHOOT)

    transactions = list(StockTransaction.by_product(product_case, to_ts(overshoot_start), to_ts(window_end)))
    transactions.sort(key=lambda tx: (tx.received_on, tx.processing_order))

    return _compute_consumption(transactions, window_start, get_base_action, {'min_periods': MIN_PERIODS, 'min_window': MIN_WINDOW})

def _compute_consumption(transactions, window_start, get_base_action, params={}):
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

