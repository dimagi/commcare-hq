from casexml.apps.stock.consumption import ConsumptionConfiguration, compute_daily_consumption
from casexml.apps.stock.tests.mock_consumption import now
from casexml.apps.stock.tests.base import StockTestBase
from corehq.form_processor.tests.utils import sharded


@sharded
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

    def testDefaultValue(self):
        self._stock_report(25, 5)
        self._stock_report(10, 0)

        self.assertEqual(None, compute_daily_consumption(
            self.domain.name, self.case_id, self.product_id, now,
            configuration=ConsumptionConfiguration(min_periods=4)
        ))
