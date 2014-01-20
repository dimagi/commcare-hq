from casexml.apps.stock.tests.base import StockTestBase


class ConsumptionCaseTest(StockTestBase):

    def testNoConsumption(self):
        self._stock_report(25, 5)
        self._stock_report(25, 0)
        self.assertAlmostEqual(0., self._compute_consumption())

    def testNoConsumptionWithReceipts(self):
        self._stock_report(25, 5)
        self._receipt_report(10, 3)
        self._stock_report(35, 0)
        self.assertAlmostEqual(0., self._compute_consumption())

    def testSimpleConsumption(self):
        self._stock_report(25, 5)
        self._stock_report(10, 0)
        self.assertAlmostEqual(3., self._compute_consumption())


