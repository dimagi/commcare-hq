from custom.ilsgateway.models import SupplyPointStatus, SupplyPointStatusValues, SupplyPointStatusTypes
from custom.ilsgateway.tanzania.reminders import SUBMITTED_REMINDER_DISTRICT, SUBMITTED_NOTIFICATION_MSD, \
    SUBMITTED_CONFIRM, NOT_SUBMITTED_CONFIRM
from custom.ilsgateway.tests import ILSTestScript


class ILSRandRTest(ILSTestScript):

    def setUp(self):
        super(ILSRandRTest, self).setUp()

    def test_randr_submitted_district(self):
        script = """
          555 > nimetuma
          555 < {0}
          111 < {1}
        """.format(unicode(SUBMITTED_REMINDER_DISTRICT),
                   unicode(SUBMITTED_NOTIFICATION_MSD) % {"district_name": self.dis.name,
                                                          "group_a": 0,
                                                          "group_b": 0,
                                                          "group_c": 0})
        self.run_script(script)

        sps = SupplyPointStatus.objects.filter(location_id=self.dis.get_id,
                                               status_type="rr_dist").order_by("-status_date")[0]

        self.assertEqual(SupplyPointStatusValues.SUBMITTED, sps.status_value)
        self.assertEqual(SupplyPointStatusTypes.R_AND_R_DISTRICT, sps.status_type)

    def test_randr_submitted_district_with_amounts(self):
        script = """
          555 > nimetuma a 10 b 11 c 12
          555 < {0}
          111 < {1}
        """.format(unicode(SUBMITTED_CONFIRM) % {"contact_name": self.user_dis.name, "sp_name": self.dis.name},
                   unicode(SUBMITTED_NOTIFICATION_MSD) % {"district_name": self.dis.name,
                                                          "group_a": 10,
                                                          "group_b": 11,
                                                          "group_c": 12})
        self.run_script(script)

        sps = SupplyPointStatus.objects.filter(location_id=self.dis.get_id,
                                               status_type="rr_dist").order_by("-status_date")[0]

        self.assertEqual(SupplyPointStatusValues.SUBMITTED, sps.status_value)
        self.assertEqual(SupplyPointStatusTypes.R_AND_R_DISTRICT, sps.status_type)

    def test_randr_submitted_facility(self):

        script = """
          5551234 > nimetuma
          5551234 < {0}
        """.format(unicode(SUBMITTED_CONFIRM) % {"contact_name": self.user_fac1.name,
                                                 "sp_name": self.loc1.name})
        self.run_script(script)

        sps = SupplyPointStatus.objects.filter(location_id=self.loc1.get_id,
                                               status_type="rr_fac").order_by("-status_date")[0]

        self.assertEqual(SupplyPointStatusValues.SUBMITTED, sps.status_value)
        self.assertEqual(SupplyPointStatusTypes.R_AND_R_FACILITY, sps.status_type)

    def test_randr_not_submitted(self):

        script = """
          5551234 > sijatuma
          5551234 < {0}
        """.format(unicode(NOT_SUBMITTED_CONFIRM))
        self.run_script(script)

        sps = SupplyPointStatus.objects.filter(location_id=self.loc1.get_id,
                                               status_type="rr_fac").order_by("-status_date")[0]

        self.assertEqual(SupplyPointStatusValues.NOT_SUBMITTED, sps.status_value)
        self.assertEqual(SupplyPointStatusTypes.R_AND_R_FACILITY, sps.status_type)
