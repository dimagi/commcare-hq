from django.test import SimpleTestCase
from casexml.apps.stock.tests.mock_consumption import mock_consumption, ago
from corehq.form_processor.models import LedgerTransaction


class ConsumptionCalcTest(SimpleTestCase):

    def consumption(self, txdata, window, params=None):
        consumption_tx_data = []
        exclude_inferred_receipts = params.get('exclude_invalid_periods', False) if params else False
        for tx in txdata:
            consumption_tx_data.extend(tx.get_consumption_transactions(
                exclude_inferred_receipts)
            )
        return mock_consumption(consumption_tx_data, window, params)

    def test_one_period(self):
        self.assertAlmostEqual(
            self.consumption([
                _tx_new(LedgerTransaction.TYPE_BALANCE, 25, 25, 5),
                _tx_new(LedgerTransaction.TYPE_BALANCE, 0, 25, 0)
            ], 60), 0.)
        self.assertAlmostEqual(
            self.consumption([
                _tx_new(LedgerTransaction.TYPE_BALANCE, 25, 25, 5),
                _tx_new(LedgerTransaction.TYPE_BALANCE, 10, 35, 0),
            ], 60), 0.)
        # 15 / 5 = 3
        self.assertAlmostEqual(
            self.consumption([
                _tx_new(LedgerTransaction.TYPE_BALANCE, 25, 25, 5),
                _tx_new(LedgerTransaction.TYPE_BALANCE, -15, 10, 0),
            ], 60), 3.)
        # 27 / 5 = 5.4
        self.assertAlmostEqual(
            self.consumption([
                _tx_new(LedgerTransaction.TYPE_BALANCE, 25, 25, 5),
                _tx_new(LedgerTransaction.TYPE_TRANSFER, 12, 37, 3),
                _tx_new(LedgerTransaction.TYPE_BALANCE, -27, 10, 0),
            ], 60), 5.4)
        # (6 + 21) / 5 = 5.4
        self.assertAlmostEqual(
            self.consumption([
                _tx_new(LedgerTransaction.TYPE_BALANCE, 25, 25, 5),
                _tx_new(LedgerTransaction.TYPE_TRANSFER, -6, 19, 3),
                _tx_new(LedgerTransaction.TYPE_TRANSFER, 12, 31, 3),
                _tx_new(LedgerTransaction.TYPE_BALANCE, -21, 10, 0),
            ], 60), 5.4)

    def test_one_period_with_receipts(self):
        self.assertIsNone(
            self.consumption([
                _tx_new(LedgerTransaction.TYPE_BALANCE, 25, 25, 5),
                _tx_new(LedgerTransaction.TYPE_TRANSFER, 10, 35, 0),
                _tx_new(LedgerTransaction.TYPE_BALANCE, 5, 40, 0),  # invalid
            ], 60, {'exclude_invalid_periods': True}))

        self.assertIsNotNone(
            self.consumption([
                _tx_new(LedgerTransaction.TYPE_BALANCE, 25, 25, 5),
                _tx_new(LedgerTransaction.TYPE_TRANSFER, 10, 35, 0),
                _tx_new(LedgerTransaction.TYPE_BALANCE, 5, 40, 0),  # invalid
            ], 60)
        )

    def test_multiple_periods(self):
        self.assertAlmostEqual(
            self.consumption([
                _tx_new(LedgerTransaction.TYPE_BALANCE, 25, 25, 15),

                _tx_new(LedgerTransaction.TYPE_TRANSFER, -4, 21, 12),
                _tx_new(LedgerTransaction.TYPE_BALANCE, 12, 33, 12),

                _tx_new(LedgerTransaction.TYPE_TRANSFER, -30, 3, 7),
                _tx_new(LedgerTransaction.TYPE_BALANCE, 3, 6, 7),

                _tx_new(LedgerTransaction.TYPE_TRANSFER, -10, -4, 0),
                _tx_new(LedgerTransaction.TYPE_BALANCE, 14, 10, 0),
            ], 60), 44 / 15)

    def test_excluded_period(self):
        self.assertAlmostEqual(self.consumption([
            _tx_new(LedgerTransaction.TYPE_BALANCE, 25, 25, 15),

            _tx_new(LedgerTransaction.TYPE_TRANSFER, -4, 21, 12),
            _tx_new(LedgerTransaction.TYPE_BALANCE, 12, 33, 12),

            _tx_new(LedgerTransaction.TYPE_TRANSFER, 36, -3, 7),
            _tx_new(LedgerTransaction.TYPE_BALANCE, 3, 0, 7),  # stockout

            _tx_new(LedgerTransaction.TYPE_TRANSFER, -5, -5, 5),
            _tx_new(LedgerTransaction.TYPE_BALANCE, 25, 20, 5),  # restock, consumption days 12-5 ignored

            _tx_new(LedgerTransaction.TYPE_TRANSFER, -10, 10, 0),
            _tx_new(LedgerTransaction.TYPE_BALANCE, 14, 24, 0),
        ], 60), 1.75)

    def test_prorated_period(self):
        tx_past_window = [
            _tx_new(LedgerTransaction.TYPE_BALANCE, 200, 200, 65),

            _tx_new(LedgerTransaction.TYPE_TRANSFER, -100, 100, 50),
            _tx_new(LedgerTransaction.TYPE_BALANCE, 50, 150, 50),

            _tx_new(LedgerTransaction.TYPE_TRANSFER, -20, 130, 0),
            _tx_new(LedgerTransaction.TYPE_BALANCE, 30, 160, 0),
        ]
        self.assertAlmostEqual(self.consumption(tx_past_window, 60), 1.44444444)
        self.assertAlmostEqual(self.consumption(tx_past_window, 55), 0.96969696)

    def test_thresholds(self):
        tx = [
            _tx_new(LedgerTransaction.TYPE_BALANCE, 25, 25, 15),

            _tx_new(LedgerTransaction.TYPE_TRANSFER, -4, 21, 12),
            _tx_new(LedgerTransaction.TYPE_BALANCE, 12, 33, 12),

            _tx_new(LedgerTransaction.TYPE_TRANSFER, -30, 3, 7),
            _tx_new(LedgerTransaction.TYPE_BALANCE, 3, 6, 7),

            _tx_new(LedgerTransaction.TYPE_TRANSFER, -10, -4, 0),
            _tx_new(LedgerTransaction.TYPE_BALANCE, 14, 10, 0),
        ]
        self.assertEqual(self.consumption(tx, 60, {'min_periods': 4}), None)
        self.assertAlmostEqual(self.consumption(tx, 60, {'min_periods': 3}), 44 / 15)
        self.assertEqual(self.consumption(tx, 60, {'min_window': 16}), None)
        self.assertAlmostEqual(self.consumption(tx, 60, {'min_window': 15}), 44 / 15)


def _tx_new(type_, delta, updated_balance, age):
    return LedgerTransaction(
        type=type_,
        delta=delta,
        updated_balance=updated_balance,
        report_date=ago(age)
    )
