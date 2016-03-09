from datetime import datetime

from casexml.apps.stock.models import StockTransaction
from corehq.apps.commtrack.models import StockState
from custom.ilsgateway.tanzania.reminders import SOH_CONFIRM, STOCKOUT_CONFIRM
from custom.ilsgateway.tests.handlers.utils import ILSTestScript


class TestStockout(ILSTestScript):

    def test_stockout(self):

        supply_point_id = self.loc1.sql_location.supply_point_id

        script = """
            5551234 > Hmk Id 400 Dp 569 Ip 678
            5551234 < %(soh_confirm)s
        """ % {"soh_confirm": unicode(SOH_CONFIRM)}
        self.run_script(script)
        self.assertEqual(StockTransaction.objects.filter(case_id=self.facility_sp_id).count(), 3)
        self.assertEqual(StockState.objects.filter(case_id=self.facility_sp_id).count(), 3)

        quantities = [400, 569, 678]
        for (idx, stock_transaction) in enumerate(StockTransaction.objects.all().order_by('pk')):
            self.assertEqual(stock_transaction.case_id, supply_point_id)
            self.assertEqual(stock_transaction.stock_on_hand, quantities[idx])
        now = datetime.utcnow()
        script = """
            5551234 > stockout id dp ip
            5551234 < {}
        """.format(STOCKOUT_CONFIRM % {
            "contact_name": self.user1.full_name,
            "product_names": "id dp ip",
            "facility_name": self.loc1.name
        })
        self.run_script(script)

        for stock_transaction in StockTransaction.objects.filter(report__date__gte=now):
            self.assertEqual(stock_transaction.case_id, supply_point_id)
            self.assertEqual(stock_transaction.stock_on_hand, 0)
