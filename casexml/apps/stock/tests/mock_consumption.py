from dimagi.utils import parsing as dateparse
from datetime import datetime, timedelta
from casexml.apps.stock.consumption import compute_consumption_from_transactions
import collections

to_ts = dateparse.json_format_datetime

MockTransaction = collections.namedtuple('MockTransaction', ['action', 'value', 'received_on'])
mock_transaction = collections.namedtuple('tx', ['action', 'value', 'age'])

now = datetime.utcnow()
def ago(days):
    return now - timedelta(days=days)


# note that you must add inferred consumption transactions manually to txdata
def mock_consumption(txdata, window, params={}):
    return compute_consumption_from_transactions(
        [MockTransaction(tx.action, tx.value, ago(tx.age)) for tx in txdata],
        ago(window),
        lambda action: action,
        params,
    )



