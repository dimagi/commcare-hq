from corehq.apps.commtrack.models import StockState
from custom.ilsgateway.models import SupplyPointStatus, SupplyPointStatusValues, SupplyPointStatusTypes
from custom.ilsgateway.tanzania.reminders import DELIVERY_PARTIAL_CONFIRM, NOT_DELIVERED_CONFIRM, \
    DELIVERY_CONFIRM_DISTRICT, DELIVERY_CONFIRM_CHILDREN
from custom.ilsgateway.tanzania.test.utils import ILSTestScript


class ILSDeliveredTest(ILSTestScript):

    def setUp(self):
        super(ILSDeliveredTest, self).setUp()

    def testDeliveryFacilityReceivedNoQuantitiesReported(self):

        script = """
            5551234 > delivered
            5551234 < {0}
        """.format(DELIVERY_PARTIAL_CONFIRM)
        self.run_script(script)

        sp = self.loc1.linked_supply_point()
        sps = SupplyPointStatus.objects.filter(supply_point=sp.get_id,
                                               status_type="del_fac").order_by("-status_date")[0]

        self.assertEqual(SupplyPointStatusValues.RECEIVED, sps.status_value)
        self.assertEqual(SupplyPointStatusTypes.DELIVERY_FACILITY, sps.status_type)

    def testDeliveryFacilityReceivedQuantitiesReported(self):

        script = """
            5551234 > delivered jd 400 mc 569
            5551234 < {0}
            """.format("received stock report for loc1(Test Facility 1) R jd400 mc569")
        self.run_script(script)
        self.assertEqual(2, StockState.objects.count())
        for ps in StockState.objects.all():
            self.assertEqual(self.loc1.linked_supply_point().get_id, ps.case_id)
            self.assertTrue(0 != ps.stock_on_hand)

    def testDeliveryFacilityNotReceived(self):

        script = """
            5551234 > sijapokea
            5551234 < {0}
            """.format(NOT_DELIVERED_CONFIRM)
        self.run_script(script)

        sp = self.loc1.linked_supply_point()
        sps = SupplyPointStatus.objects.filter(supply_point=sp.get_id,
                                         status_type="del_fac").order_by("-status_date")[0]

        self.assertEqual(SupplyPointStatusValues.NOT_RECEIVED, sps.status_value)
        self.assertEqual(SupplyPointStatusTypes.DELIVERY_FACILITY, sps.status_type)

    def testDeliveryDistrictReceived(self):

        script = """
          555 > nimepokea
          555 < {0}
          5551234 < {1}
          5555678 < {1}
        """.format(DELIVERY_CONFIRM_DISTRICT % dict(contact_name="{0} {1}".format(self.user_dis.first_name,
                                                                                  self.user_dis.last_name),
                                                    facility_name=self.dis.name),
                   DELIVERY_CONFIRM_CHILDREN % dict(district_name=self.dis.name))

        self.run_script(script)

        sp = self.dis.linked_supply_point()
        sps = SupplyPointStatus.objects.filter(supply_point=sp.get_id,
                                         status_type="del_dist").order_by("-status_date")[0]

        self.assertEqual(SupplyPointStatusValues.RECEIVED, sps.status_value)
        self.assertEqual(SupplyPointStatusTypes.DELIVERY_DISTRICT, sps.status_type)

    def testDeliveryDistrictNotReceived(self):

        script = """
          555 > sijapokea
          555 < {0}
        """.format(NOT_DELIVERED_CONFIRM)
        self.run_script(script)

        sp = self.dis.linked_supply_point()
        sps = SupplyPointStatus.objects.filter(supply_point=sp.get_id,
                                         status_type="del_dist").order_by("-status_date")[0]

        self.assertEqual(SupplyPointStatusValues.NOT_RECEIVED, sps.status_value)
        self.assertEqual(SupplyPointStatusTypes.DELIVERY_DISTRICT, sps.status_type)

