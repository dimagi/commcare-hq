from corehq.apps.commtrack.models import StockState
from corehq.util.translation import localize
from custom.ilsgateway.tanzania.reminders import LANGUAGE_CONFIRM, SOH_CONFIRM
from custom.ilsgateway.tests.handlers.utils import ILSTestScript


class TranslationTest(ILSTestScript):

    def setUp(self):
        super(TranslationTest, self).setUp()

    def test_soh(self):
        with localize('sw'):
            response1 = unicode(SOH_CONFIRM)
        script = """
            5551234 > soh jd 400 mc 569
            5551234 < {0}
        """.format(response1)
        self.run_script(script)

        self.run_script(script)
        self.assertEqual(2, StockState.objects.count())
        for ps in StockState.objects.all():
            self.assertEqual(self.user_fac1.location.linked_supply_point().get_id, ps.case_id)
            self.assertTrue(0 != ps.stock_on_hand)

    def test_soh_in_swahili(self):
        self.user_fac1.language = 'en'
        self.user_fac1.save()
        with localize('sw'):
            response1 = unicode(LANGUAGE_CONFIRM)
            response2 = unicode(SOH_CONFIRM)

        language_message = """
            5551234 > language sw
            5551234 < {0}
        """.format(response1 % dict(language='Swahili'))
        self.run_script(language_message)

        soh_script = """
            5551234 > hmk jd 400 mc 569
            5551234 < {0}
        """.format(response2)
        self.run_script(soh_script)
