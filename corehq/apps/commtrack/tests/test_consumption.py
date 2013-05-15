from corehq.apps.commtrack.tests.util import CommTrackTest
from corehq.pillows.commtrack import _compute_consumption
from dimagi.utils import parsing as dateparse
from datetime import datetime, timedelta
import collections
to_ts = dateparse.json_format_datetime

MockTransaction = collections.namedtuple('MockTransaction', ['action', 'value', 'received_on'])
_tx = collections.namedtuple('tx', ['action', 'value', 'age'])

# note that you must add inferred consumption transactions manually to txdata
def consumption(txdata, window, params={}):
    now = datetime.utcnow()
    def ago(days):
        return now - timedelta(days=days)
    
    return _compute_consumption(
        [MockTransaction(tx.action, tx.value, ago(tx.age)) for tx in txdata],
        ago(window),
        lambda action: action,
        params
    )

class ConsumptionTest(CommTrackTest):

    def test_one_period(self):
        self.assertAlmostEqual(consumption([
                _tx('stockonhand', 25, 5),
                _tx('stockonhand', 25, 0),
            ], 60), 0.)
        self.assertAlmostEqual(consumption([
                _tx('stockonhand', 25, 5),
                _tx('receipts', 10, 0),
                _tx('stockonhand', 35, 0),
            ], 60), 0.)
        self.assertAlmostEqual(consumption([
                _tx('stockonhand', 25, 5),
                _tx('consumption', 15, 0),
                _tx('stockonhand', 10, 0),
            ], 60), 3.)
        self.assertAlmostEqual(consumption([
                _tx('stockonhand', 25, 5),
                _tx('receipts', 12, 3),
                _tx('consumption', 27, 0),
                _tx('stockonhand', 10, 0),
            ], 60), 5.4)
        self.assertAlmostEqual(consumption([
                _tx('stockonhand', 25, 5),
                _tx('consumption', 6, 3),
                _tx('receipts', 12, 3),
                _tx('consumption', 21, 0),
                _tx('stockonhand', 10, 0),
            ], 60), 5.4)

    def test_multiple_periods(self):
        self.assertAlmostEqual(consumption([
                _tx('stockonhand', 25, 15),

                _tx('consumption', 4, 12),
                _tx('receipts', 12, 12),
                _tx('stockonhand', 33, 12),

                _tx('consumption', 30, 7),
                _tx('receipts', 3, 7),
                _tx('stockonhand', 6, 7),

                _tx('consumption', 10, 0),
                _tx('receipts', 14, 0),
                _tx('stockonhand', 10, 0),
            ], 60), 44/15.)

    def test_excluded_period(self):
        self.assertAlmostEqual(consumption([
                _tx('stockonhand', 25, 15),

                _tx('consumption', 4, 12),
                _tx('receipts', 12, 12),
                _tx('stockonhand', 33, 12),

                _tx('consumption', 36, 7),
                _tx('receipts', 3, 7),
                _tx('stockout', 0, 7), # stockout

                _tx('consumption', 5, 5),
                _tx('receipts', 25, 5), # restock, consumption days 12-5 ignored
                _tx('stockonhand', 20, 5),

                _tx('consumption', 10, 0),
                _tx('receipts', 14, 0),
                _tx('stockonhand', 24, 0),
            ], 60), 1.75)

    def test_prorated_period(self):
        tx_past_window = [
            _tx('stockonhand', 200, 65),

            _tx('consumption', 100, 50),
            _tx('receipts', 50, 50),
            _tx('stockonhand', 150, 50),
            
            _tx('consumption', 20, 0),
            _tx('receipts', 30, 0),
            _tx('stockonhand', 160, 0),
        ]
        self.assertAlmostEqual(consumption(tx_past_window, 60), 1.44444444)
        self.assertAlmostEqual(consumption(tx_past_window, 55), 0.96969696)

    def test_thresholds(self):
        tx = [
            _tx('stockonhand', 25, 15),
            
            _tx('consumption', 4, 12),
            _tx('receipts', 12, 12),
            _tx('stockonhand', 33, 12),
            
            _tx('consumption', 30, 7),
            _tx('receipts', 3, 7),
            _tx('stockonhand', 6, 7),
            
            _tx('consumption', 10, 0),
            _tx('receipts', 14, 0),
            _tx('stockonhand', 10, 0),
        ]
        self.assertEqual(consumption(tx, 60, {'min_periods': 4}), None)
        self.assertAlmostEqual(consumption(tx, 60, {'min_periods': 3}), 44/15.)
        self.assertEqual(consumption(tx, 60, {'min_window': 16}), None)
        self.assertAlmostEqual(consumption(tx, 60, {'min_window': 15}), 44/15.)
