from casexml.apps.stock.models import StockTransaction
from corehq.apps.commtrack.models import StockState
from custom.ilsgateway.tanzania.reminders import SOH_CONFIRM, STOCKOUT_CONFIRM
from custom.ilsgateway.tests.handlers.utils import ILSTestScript


class TestStockout(ILSTestScript):

    def test_stockout(self):

        script = """
            5551234 > Hmk Id 400 Dp 569 Ip 678
            5551234 < %(soh_confirm)s
        """ % {"soh_confirm": unicode(SOH_CONFIRM)}
        self.run_script(script)
        self.assertEqual(StockTransaction.objects.all().count(), 3)
        self.assertEqual(StockState.objects.all().count(), 3)

        for stock_transaction in StockTransaction.objects.all():
            self.assertTrue(stock_transaction.stock_on_hand != 0)

        script = """
            5551234 > stockout id dp ip
            5551234 < {}
        """.format(STOCKOUT_CONFIRM % {
            "contact_name": self.user1.full_name,
            "product_names": "id dp ip",
            "facility_name": self.loc1.name
        })
        self.run_script(script)
