from __future__ import absolute_import
from __future__ import unicode_literals
from casexml.apps.stock import const
from casexml.apps.stock.models import StockTransaction
from casexml.apps.stock.tests.base import StockTestBase


class InferredTransactionsTest(StockTestBase):

    def testFirstConsumption(self):
        self._stock_report(25, 5)
        self.assertEqual(1, StockTransaction.objects.count())
        txn = StockTransaction.objects.all()[0]
        self.assertEqual(const.TRANSACTION_TYPE_STOCKONHAND, txn.type)
        self.assertEqual(25, txn.stock_on_hand)
        self.assertEqual(0, txn.quantity)

    def testNoConsumptionChange(self):
        self._stock_report(25, 5)
        self._stock_report(25, 0)
        self.assertEqual(2, StockTransaction.objects.count())
        for txn in StockTransaction.objects.all():
            self.assertEqual(const.TRANSACTION_TYPE_STOCKONHAND, txn.type)
            self.assertEqual(25, txn.stock_on_hand)
            self.assertEqual(0, txn.quantity)

    def testInferredConsumption(self):
        self._stock_report(25, 5)
        self._stock_report(10, 0)
        self.assertEqual(3, StockTransaction.objects.count())
        (soh1, cons, soh2) = StockTransaction.objects.order_by('report__date', 'pk')
        self.assertEqual(const.TRANSACTION_TYPE_STOCKONHAND, soh1.type)
        self.assertEqual(25, soh1.stock_on_hand)
        self.assertEqual(0, soh1.quantity)

        self.assertEqual(const.TRANSACTION_TYPE_CONSUMPTION, cons.type)
        self.assertEqual(10, cons.stock_on_hand)
        self.assertEqual(-15, cons.quantity)
        self.assertEqual(const.TRANSACTION_SUBTYPE_INFERRED, cons.subtype)

        self.assertEqual(const.TRANSACTION_TYPE_STOCKONHAND, soh2.type)
        self.assertEqual(10, soh2.stock_on_hand)
        self.assertEqual(0, soh2.quantity)
        self.assertEqual(cons.report, soh2.report)
        self.assertEqual(cons.case_id, soh2.case_id)
        self.assertEqual(cons.product_id, soh2.product_id)

    def testInferredReceipt(self):
        self._stock_report(25, 5)
        self._stock_report(40, 0)
        self.assertEqual(3, StockTransaction.objects.count())
        (soh1, rec, soh2) = StockTransaction.objects.order_by('report__date', 'pk')
        self.assertEqual(const.TRANSACTION_TYPE_STOCKONHAND, soh1.type)
        self.assertEqual(25, soh1.stock_on_hand)
        self.assertEqual(0, soh1.quantity)

        self.assertEqual(const.TRANSACTION_TYPE_RECEIPTS, rec.type)
        self.assertEqual(40, rec.stock_on_hand)
        self.assertEqual(15, rec.quantity)
        self.assertEqual(const.TRANSACTION_SUBTYPE_INFERRED, rec.subtype)

        self.assertEqual(const.TRANSACTION_TYPE_STOCKONHAND, soh2.type)
        self.assertEqual(40, soh2.stock_on_hand)
        self.assertEqual(0, soh2.quantity)
        self.assertEqual(rec.report, soh2.report)
        self.assertEqual(rec.case_id, soh2.case_id)
        self.assertEqual(rec.product_id, soh2.product_id)
