from pillowtop.listener import BasicPillow
from couchforms.models import XFormInstance
from corehq.apps.commtrack.models import StockTransaction
import collections
from dimagi.utils import parsing as dateparse
from datetime import datetime, timedelta

class ConsumptionRatePillow(BasicPillow):
    document_class = XFormInstance
    couch_filter = 'commtrack/stock_reports'

    def change_transform(self, doc_dict):
        txs = doc_dict['form']['transaction']
        if not isinstance(txs, collections.Sequence):
            txs = [txs]
        touched_products = set(tx['product_entry'] for tx in txs)

        for case_id in touched_products:
            compute_consumption(case_id, doc_dict['received_on'])

CONSUMPTION_WINDOW = 60 # days
WINDOW_OVERSHOOT = 15 # days

def compute_consumption(product_case, window_end):
    window_start = dateparse.json_format_datetime(dateparse.string_to_datetime(window_end) - timedelta(days=CONSUMPTION_WINDOW + WINDOW_OVERSHOOT))
    transactions = StockTransaction.by_product(product_case, window_start, window_end)

    for tx in transactions:
        print tx._doc
    print
    print

    return 555

