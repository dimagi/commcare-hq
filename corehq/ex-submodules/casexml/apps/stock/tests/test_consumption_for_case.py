from __future__ import absolute_import
from casexml.apps.stock.consumption import (ConsumptionConfiguration, compute_daily_consumption,
    compute_consumption_or_default)
from casexml.apps.stock.tests.mock_consumption import now
from casexml.apps.stock.tests.base import StockTestBase
from corehq.form_processor.tests.utils import use_sql_backend


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
            self.domain.name, self.case_id, self.product_id,
            now, configuration=ConsumptionConfiguration(min_periods=4))
        )
        _ten = lambda case_id, product_id: 10
        self.assertAlmostEqual(10., compute_consumption_or_default(
            self.domain.name,
            self.case_id,
            self.product_id,
            now,
            configuration=ConsumptionConfiguration(
                min_periods=4,
                default_monthly_consumption_function=_ten
            )
        ))


@use_sql_backend
class ConsumptionCaseTestSQL(ConsumptionCaseTest):
    pass
