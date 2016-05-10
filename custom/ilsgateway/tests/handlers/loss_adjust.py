from corehq.apps.commtrack.models import StockState
from casexml.apps.stock.models import StockReport
from corehq.util.translation import localize
from custom.ilsgateway.tanzania.reminders import LOSS_ADJUST_CONFIRM, SOH_CONFIRM, LOSS_ADJUST_NO_SOH
from custom.ilsgateway.tests.handlers.utils import ILSTestScript


class ILSLossesAdjustmentsTest(ILSTestScript):

    def tearDown(self):
        StockReport.objects.all().delete()
        StockState.objects.all().delete()

    def test_losses_adjustments_without_soh(self):
        with localize('sw'):
            response = unicode(LOSS_ADJUST_NO_SOH)
        script = """
            5551234 > um ID -3 dp -5 IP 13
            5551234 < {0}
        """.format(response % {'products_list': 'dp, id, ip'})
        self.run_script(script)

    def test_losses_adjustments(self):
        with localize('sw'):
            response1 = unicode(SOH_CONFIRM)
            response2 = unicode(LOSS_ADJUST_CONFIRM)

        sohs = {
            'id': 400,
            'dp': 569,
            'ip': 678
        }
        script = """
            5551234 > Hmk Id 400 Dp 569 Ip 678
            5551234 < {0}
        """.format(response1)
        self.run_script(script)

        self.assertEqual(StockState.objects.filter(case_id=self.facility_sp_id).count(), 3)
        for ps in StockState.objects.all():
            self.assertEqual(self.user_fac1.location.linked_supply_point().get_id, ps.case_id)
            self.assertEqual(ps.stock_on_hand, sohs[ps.sql_product.code])

        script = """
            5551234 > um ID -3 dp -5 IP 13
            5551234 < {0}
        """.format(response2)
        self.run_script(script)

        self.assertEqual(StockState.objects.filter(case_id=self.facility_sp_id).count(), 3)

        self.assertEqual(StockState.objects.get(sql_product__code="id").stock_on_hand, 397)
        self.assertEqual(
            StockState.objects.get(sql_product__code="dp", case_id=self.facility_sp_id).stock_on_hand,
            564
        )
        self.assertEqual(StockState.objects.get(sql_product__code="ip").stock_on_hand, 691)

    def test_losses_adjustments_la_word(self):
        with localize('sw'):
            response1 = unicode(SOH_CONFIRM)
            response2 = unicode(LOSS_ADJUST_CONFIRM)

        sohs = {
            'id': 400,
            'dp': 569,
            'ip': 678
        }

        script = """
            5551234 > Hmk Id 400 Dp 569 Ip 678
            5551234 < {0}
        """.format(response1)
        self.run_script(script)

        self.assertEqual(StockState.objects.filter(case_id=self.facility_sp_id).count(), 3)
        for ps in StockState.objects.all():
            self.assertEqual(self.user_fac1.location.linked_supply_point().get_id, ps.case_id)
            self.assertEqual(ps.stock_on_hand, sohs[ps.sql_product.code])

        script = """
            5551234 > la id -3 dp -5 ip 13
            5551234 < {0}
        """.format(response2)
        self.run_script(script)

        self.assertEqual(StockState.objects.filter(case_id=self.facility_sp_id).count(), 3)

        self.assertEqual(StockState.objects.get(sql_product__code="id").stock_on_hand, 397)
        self.assertEqual(StockState.objects.get(sql_product__code="dp").stock_on_hand, 564)
        self.assertEqual(StockState.objects.get(sql_product__code="ip").stock_on_hand, 691)
