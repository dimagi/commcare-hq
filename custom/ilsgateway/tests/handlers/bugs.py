from datetime import datetime

from django.utils import translation
from django.utils.translation import ugettext as _

from casexml.apps.stock.models import StockTransaction
from custom.ilsgateway.tanzania.reminders import SOH_CONFIRM
from custom.ilsgateway.tests import ILSTestScript


class TestBugs(ILSTestScript):

    def test_unicode_characters(self):
        translation.activate('sw')
        script = u"""
            5551234 > Hmk Id 400 \u0660Dp 569 Ip 678
            5551234 < %(soh_confirm)s
        """ % {"soh_confirm": _(SOH_CONFIRM)}

        now = datetime.utcnow()
        self.run_script(script)

        txs = list(StockTransaction.objects.filter(
            case_id=self.loc1.sql_location.supply_point_id,
            report__date__gte=now)
        )
        self.assertEqual(len(txs), 3)

        self.assertSetEqual(
            {(tx.sql_product.code, int(tx.stock_on_hand)) for tx in txs},
            {('id', 400), ('dp', 569), ('ip', 678)}
        )
