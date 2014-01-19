import functools
import uuid
from django.test import TestCase
from casexml.apps.stock import const
from casexml.apps.stock.consumption import compute_consumption, expand_transactions
from casexml.apps.stock.models import StockReport, StockTransaction
from casexml.apps.stock.tests.mock_consumption import ago, now
from casexml.apps.stock.tests.mock_consumption import mock_transaction as _tx

class ConsumptionCaseTestBase(TestCase):

    def setUp(self):
        # create case
        self.case_id = uuid.uuid4()
        self.product_id = uuid.uuid4()
        self._stock_report = functools.partial(_stock_report, self.case_id, self.product_id)

    def _expand_transactions(self):
        return list(expand_transactions(self.case_id, self.product_id, now))


class TransactionExpansionTest(ConsumptionCaseTestBase):

    def assertTransactionListsEqual(self, expected_list, actual_list):
        self.assertEqual(len(expected_list), len(actual_list))
        for i, actual in enumerate(actual_list):
            expected = expected_list[i]
            self.assertEqual(expected.action, actual.action)
            self.assertEqual(expected.value, actual.value)
            self.assertEqual(expected.received_on, actual.received_on)

    def testNoConsumption(self):
        self._stock_report(25, 5)
        self._stock_report(25, 0)
        expected = [
            _tx('stockonhand', 25, 5),
            _tx('stockonhand', 25, 0),
        ]
        self.assertTransactionListsEqual(expected, self._expand_transactions())
