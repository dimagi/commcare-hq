from __future__ import absolute_import
from custom.ewsghana.reminders import REQ_SUBMITTED
from custom.ewsghana.tests.handlers.utils import EWSScriptTest
import six

TEST_DOMAIN = 'ewsghana-receipts-test'


class RequisitionStatusTest(EWSScriptTest):

    def test_receipts(self):
        a = """
           5551234 > yes
           5551234 < %s
        """ % six.text_type(REQ_SUBMITTED)
        self.run_script(a)
