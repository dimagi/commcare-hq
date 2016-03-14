from corehq.apps.commtrack.models import StockState
from corehq.util.translation import localize
from custom.ilsgateway.models import SupplyPointStatus, SupplyPointStatusValues, SupplyPointStatusTypes
from custom.ilsgateway.tanzania.reminders import DELIVERY_PARTIAL_CONFIRM, NOT_DELIVERED_CONFIRM, \
    DELIVERY_CONFIRM_DISTRICT, DELIVERY_CONFIRM_CHILDREN, INVALID_PRODUCT_CODE, DELIVERED_CONFIRM
from custom.ilsgateway.tests.handlers.utils import ILSTestScript


class ILSDeliveredTest(ILSTestScript):

    def setUp(self):
        super(ILSDeliveredTest, self).setUp()

    def test_delivery_facility_received_no_quantities_reported(self):
        with localize('sw'):
            response = unicode(DELIVERY_PARTIAL_CONFIRM)
        script = """
            5551234 > nimepokea
            5551234 < {0}
        """.format(response)
        self.run_script(script)

        sps = SupplyPointStatus.objects.filter(location_id=self.loc1.get_id,
                                               status_type="del_fac").order_by("-status_date")[0]

        self.assertEqual(SupplyPointStatusValues.RECEIVED, sps.status_value)
        self.assertEqual(SupplyPointStatusTypes.DELIVERY_FACILITY, sps.status_type)

    def test_delivery_facility_received_quantities_reported(self):
        with localize('sw'):
            response = unicode(DELIVERED_CONFIRM)

        sohs = {
            'jd': 400,
            'mc': 569
        }
        script = """
            5551234 > delivered jd 400 mc 569
            5551234 < {0}
            """.format(response % {'reply_list': 'jd 400, mc 569'})
        self.run_script(script)
        self.assertEqual(2, StockState.objects.count())
        for ps in StockState.objects.all().order_by('pk'):
            self.assertEqual(self.loc1.linked_supply_point().get_id, ps.case_id)
            self.assertEqual(ps.stock_on_hand, sohs[ps.sql_product.code])

    def test_delivery_facility_not_received(self):
        with localize('sw'):
            response = unicode(NOT_DELIVERED_CONFIRM)

        script = """
            5551234 > sijapokea
            5551234 < {0}
            """.format(response)
        self.run_script(script)

        sps = SupplyPointStatus.objects.filter(location_id=self.loc1.get_id,
                                               status_type="del_fac").order_by("-status_date")[0]

        self.assertEqual(SupplyPointStatusValues.NOT_RECEIVED, sps.status_value)
        self.assertEqual(SupplyPointStatusTypes.DELIVERY_FACILITY, sps.status_type)

    def test_delivery_facility_report_product_error(self):
        with localize('sw'):
            response = unicode(INVALID_PRODUCT_CODE)
        script = """
            5551234 > nimepokea Ig 400 Dp 569 Ip 678
            5551234 < %(error_message)s
            """ % {'error_message': response % {"product_code": "ig"}}
        self.run_script(script)

    def test_delivery_district_received(self):
        with localize('sw'):
            response = unicode(DELIVERY_CONFIRM_DISTRICT)
            response2 = unicode(DELIVERY_CONFIRM_CHILDREN)
        script = """
          555 > nimepokea
          555 < {0}
          5551234 < {1}
          5555678 < {1}
        """.format(
            response % dict(contact_name="{0} {1}".format(
                self.user_dis.first_name,
                self.user_dis.last_name
            ), facility_name=self.dis.name),
            response2 % dict(district_name=self.dis.name)
        )

        self.run_script(script)

        sps = SupplyPointStatus.objects.filter(location_id=self.dis.get_id,
                                               status_type="del_dist").order_by("-status_date")[0]

        self.assertEqual(SupplyPointStatusValues.RECEIVED, sps.status_value)
        self.assertEqual(SupplyPointStatusTypes.DELIVERY_DISTRICT, sps.status_type)

    def test_delivery_district_not_received(self):
        with localize('sw'):
            response = unicode(NOT_DELIVERED_CONFIRM)

        script = """
          555 > sijapokea
          555 < {0}
        """.format(response)
        self.run_script(script)

        sps = SupplyPointStatus.objects.filter(location_id=self.dis.get_id,
                                               status_type="del_dist").order_by("-status_date")[0]

        self.assertEqual(SupplyPointStatusValues.NOT_RECEIVED, sps.status_value)
        self.assertEqual(SupplyPointStatusTypes.DELIVERY_DISTRICT, sps.status_type)
