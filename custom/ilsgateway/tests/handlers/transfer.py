from corehq.util.translation import localize
from custom.ilsgateway.models import SupplyPointStatus, SupplyPointStatusTypes, SupplyPointStatusValues
from custom.ilsgateway.tanzania.reminders import SOH_CONFIRM
from custom.ilsgateway.tests.handlers.utils import ILSTestScript


class TestTrans(ILSTestScript):

    def testTrans(self):
        with localize('sw'):
            response = unicode(SOH_CONFIRM)

        script = """
          5551234 > trans yes
          5551234 < %s
        """ % response
        self.run_script(script)

        script = """
          5551234 > trans no
          5551234 < %s
        """ % response
        self.run_script(script)

        self.assertEqual(SupplyPointStatus.objects.count(), 2)
        status1 = SupplyPointStatus.objects.get(status_type=SupplyPointStatusTypes.TRANS_FACILITY,
                                                status_value=SupplyPointStatusValues.NOT_SUBMITTED)
        status2 = SupplyPointStatus.objects.get(status_type=SupplyPointStatusTypes.TRANS_FACILITY,
                                                status_value=SupplyPointStatusValues.SUBMITTED)
        self.assertEqual(self.user1.location_id, status1.location_id)
        self.assertEqual(self.user1.location_id, status2.location_id)
