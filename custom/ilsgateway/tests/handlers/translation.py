from corehq.apps.commtrack.models import StockState
from corehq.util.translation import localize
from custom.ilsgateway.tanzania.reminders import LANGUAGE_CONFIRM, SOH_CONFIRM
from custom.ilsgateway.tests.handlers.utils import ILSTestScript


class TranslationTest(ILSTestScript):

    def setUp(self):
        super(TranslationTest, self).setUp()

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
