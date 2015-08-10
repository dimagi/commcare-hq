from django.utils.translation import ugettext as _
from corehq.apps.commtrack.models import StockState
from custom.ilsgateway.tanzania.reminders import SOH_THANK_YOU
from custom.ilsgateway.tests import ILSTestScript


class ILSLossesAdjustmentsTest(ILSTestScript):

    def setUp(self):
        super(ILSLossesAdjustmentsTest, self).setUp()

    def test_losses_adjustments(self):

        script = """
            5551234 > soh jd 400 mc 569
            5551234 < {0}
        """.format(unicode(SOH_THANK_YOU))
        self.run_script(script)

        self.run_script(script)
        self.assertEqual(2, StockState.objects.count())
        for ps in StockState.objects.all():
            self.assertEqual(self.user_fac1.location.linked_supply_point().get_id, ps.case_id)
            self.assertTrue(0 != ps.stock_on_hand)

        script = """
            5551234 > l jd 10 mc 69
            5551234 < {0}
        """.format(_("received stock report for loc1(Test Facility 1) L jd10 mc69"))
        self.run_script(script)

        self.assertEqual(390, StockState.objects.get(sql_product__code="jd").stock_on_hand)
        self.assertEqual(500, StockState.objects.get(sql_product__code="mc").stock_on_hand)
