from custom.ewsghana.reminders import REQ_SUBMITTED
from custom.ewsghana.tests.handlers.utils import EWSScriptTest

TEST_DOMAIN = 'ewsghana-receipts-test'


class RequisitionStatusTest(EWSScriptTest):

    def test_receipts(self):
        a = """
           5551234 > yes
           5551234 < %s
        """ % unicode(REQ_SUBMITTED)
        self.run_script(a)
