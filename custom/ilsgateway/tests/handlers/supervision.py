from corehq.util.translation import localize
from custom.ilsgateway.models import SupplyPointStatus, SupplyPointStatusTypes, SupplyPointStatusValues
from custom.ilsgateway.tanzania.reminders import SUPERVISION_CONFIRM_YES, SUPERVISION_CONFIRM_NO
from custom.ilsgateway.tests.handlers.utils import ILSTestScript


class TestSupervision(ILSTestScript):

    def test_supervision_yes(self):
        with localize('sw'):
            response = unicode(SUPERVISION_CONFIRM_YES)

        script = """
          5551234 > usimamizi ndio
          5551234 < {0}
        """.format(response)
        self.run_script(script)

        statuses = SupplyPointStatus.objects.filter(location_id=self.loc1.get_id)
        self.assertEqual(statuses.count(), 1)
        status = statuses[0]
        self.assertEqual(status.status_type, SupplyPointStatusTypes.SUPERVISION_FACILITY)
        self.assertEqual(status.status_value, SupplyPointStatusValues.RECEIVED)

    def test_supervision_no(self):
        with localize('sw'):
            response = unicode(SUPERVISION_CONFIRM_NO)

        script = """
          5551234 > usimamizi hapana
          5551234 < {0}
        """.format(response)
        self.run_script(script)

        statuses = SupplyPointStatus.objects.filter(location_id=self.loc1.get_id)
        self.assertEqual(statuses.count(), 1)
        status = statuses[0]
        self.assertEqual(status.status_type, SupplyPointStatusTypes.SUPERVISION_FACILITY)
        self.assertEqual(status.status_value, SupplyPointStatusValues.NOT_RECEIVED)
