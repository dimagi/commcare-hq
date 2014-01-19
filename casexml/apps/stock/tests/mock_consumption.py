from dimagi.utils import parsing as dateparse
from datetime import datetime, timedelta
from casexml.apps.stock.consumption import compute_consumption
import collections

to_ts = dateparse.json_format_datetime

MockTransaction = collections.namedtuple('MockTransaction', ['action', 'value', 'received_on'])
mock_transaction = collections.namedtuple('tx', ['action', 'value', 'age'])

# note that you must add inferred consumption transactions manually to txdata
def mock_consumption(txdata, window, params={}):
    now = datetime.utcnow()
    def ago(days):
        return now - timedelta(days=days)

    return compute_consumption(
        [MockTransaction(tx.action, tx.value, ago(tx.age)) for tx in txdata],
        ago(window),
        lambda action: action,
        params
    )



