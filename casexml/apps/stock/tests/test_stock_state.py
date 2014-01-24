from casexml.apps.stock.models import StockState
from casexml.apps.stock.tests.base import StockTestBase


class StockStateTest(StockTestBase):
    def test_stock_state(self):
        self._stock_report(25, 5)
        self._stock_report(10, 0)

        state = StockState.objects.get(
            section_id='stock',
            case_id=self.case_id,
            product_id=self.product_id,
        )

        self.assertEqual(10, state.stock_on_hand)
        self.assertEqual(3.0, state.daily_consumption)
