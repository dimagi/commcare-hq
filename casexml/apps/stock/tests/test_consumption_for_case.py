import functools
import uuid
from django.test import TestCase
from casexml.apps.stock import const
from casexml.apps.stock.consumption import expand_transactions, compute_consumption
from casexml.apps.stock.models import StockReport, StockTransaction
from casexml.apps.stock.tests.mock_consumption import ago, now
from casexml.apps.stock.tests.mock_consumption import mock_transaction as _tx

class ConsumptionCaseTestBase(TestCase):

    def setUp(self):
        # create case
        self.case_id = uuid.uuid4()
        self.product_id = uuid.uuid4()
        self._stock_report = functools.partial(_stock_report, self.case_id, self.product_id)
        self._receipt_report = functools.partial(_receipt_report, self.case_id, self.product_id)
        self._compute_consumption = functools.partial(compute_consumption, self.case_id, self.product_id, now)

    def _expand_transactions(self):
        return list(expand_transactions(self.case_id, self.product_id, ago(60), now))


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

    def testNoConsumptionWithReceipts(self):
        self._stock_report(25, 5)
        self._receipt_report(10, 3)
        self._stock_report(35, 0)
        expected = [
            _tx('stockonhand', 25, 5),
            _tx('receipts', 10, 3),
            _tx('stockonhand', 35, 0),
        ]
        self.assertTransactionListsEqual(expected, self._expand_transactions())

    def testSimpleConsumption(self):
        self._stock_report(25, 5)
        self._stock_report(10, 0)
        expected = [
            _tx('stockonhand', 25, 5),
            _tx('consumption', 15, 0),
            _tx('stockonhand', 10, 0),
        ]
        self.assertTransactionListsEqual(expected, self._expand_transactions())


class ConsumptionCaseTest(ConsumptionCaseTestBase):

    def testBasic(self):
        # create report and transactions
        self._stock_report(25, 5)
        self._stock_report(25, 0)
        self.assertAlmostEqual(0., self._compute_consumption())


def _stock_report(case_id, product_id, amount, days_ago):
    report = StockReport.objects.create(form_id=uuid.uuid4().hex, date=ago(days_ago),
                                        type=const.REPORT_TYPE_BALANCE)
    txn = StockTransaction(
        report=report,
        section_id=const.SECTION_TYPE_STOCK,
        type=const.TRANSACTION_TYPE_STOCKONHAND,
        case_id=case_id,
        product_id=product_id,
        stock_on_hand=amount,
    )
    previous_transaction = txn.get_previous_transaction()
    txn.quantity = txn.stock_on_hand - (previous_transaction.stock_on_hand if previous_transaction else 0)
    txn.save()


def _receipt_report(case_id, product_id, amount, days_ago):
    report = StockReport.objects.create(form_id=uuid.uuid4().hex, date=ago(days_ago),
                                        type=const.REPORT_TYPE_TRANSFER)
    txn = StockTransaction(
        report=report,
        section_id=const.SECTION_TYPE_STOCK,
        type=const.TRANSACTION_TYPE_RECEIPTS,
        case_id=case_id,
        product_id=product_id,
        quantity=amount,
    )
    previous_transaction = txn.get_previous_transaction()
    txn.stock_on_hand = (previous_transaction.stock_on_hand if previous_transaction else 0) + txn.quantity
    txn.save()
