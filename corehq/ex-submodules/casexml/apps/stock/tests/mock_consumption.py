from dimagi.utils import parsing as dateparse
from datetime import datetime, timedelta
from casexml.apps.stock.consumption import compute_daily_consumption_from_transactions, ConsumptionConfiguration
import collections

to_ts = dateparse.json_format_datetime

MockTransaction = collections.namedtuple('MockTransaction', ['action', 'value', 'received_on'])
def mock_transaction(action, value, age):
    return MockTransaction(action, value, ago(age))

now = datetime.utcnow()
def ago(days):
    return now - timedelta(days=days)


# note that you must add inferred consumption transactions manually to txdata
def mock_consumption(txdata, window, params=None):
    default_params = {'min_window': 0, 'min_periods': 0}
    params = params or {}
    default_params.update(params)
    config = ConsumptionConfiguration(**default_params)
    return compute_daily_consumption_from_transactions(
        txdata,
        ago(window),
        config,
    )



