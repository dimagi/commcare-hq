from corehq.apps.commtrack.models import StockState
from custom.ilsgateway.tanzania.reminders import SOH_THANK_YOU
from custom.ilsgateway.tests import ILSTestScript


class ILSSoHTest(ILSTestScript):

    def setUp(self):
        super(ILSSoHTest, self).setUp()

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
