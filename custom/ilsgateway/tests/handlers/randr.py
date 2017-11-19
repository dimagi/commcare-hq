from __future__ import absolute_import
from corehq.util.translation import localize
from custom.ilsgateway.models import SupplyPointStatus, SupplyPointStatusValues, SupplyPointStatusTypes
from custom.ilsgateway.tanzania.reminders import SUBMITTED_REMINDER_DISTRICT, SUBMITTED_NOTIFICATION_MSD, \
    SUBMITTED_CONFIRM, NOT_SUBMITTED_CONFIRM, SUBMITTED_INVALID_QUANTITY
from custom.ilsgateway.tests.handlers.utils import ILSTestScript
import six


class ILSRandRTest(ILSTestScript):

    def test_invalid_randr_with_amounts(self):
        with localize('sw'):
            response1 = six.text_type(SUBMITTED_INVALID_QUANTITY)
        script = """
            555 > nimetuma a dd b 11 c 12
            555 < {0}
        """ .format(response1 % {'number': 'dd'})
        self.run_script(script)
