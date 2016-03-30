from corehq.util.translation import localize
from custom.ilsgateway.models import SupplyPointStatus, SupplyPointStatusValues, SupplyPointStatusTypes
from custom.ilsgateway.tanzania.reminders import TEST_HANDLER_CONFIRM, SUBMITTED_REMINDER_FACILITY, \
    LOSS_ADJUST_HELP, TEST_HANDLER_BAD_CODE, DELIVERY_REMINDER_FACILITY, SOH_HELP_MESSAGE, SUPERVISION_REMINDER, \
    SOH_THANK_YOU, SUBMITTED_REMINDER_DISTRICT, DELIVERY_REMINDER_DISTRICT, DELIVERY_LATE_DISTRICT, \
    TEST_HANDLER_HELP
from custom.ilsgateway.tests.handlers.utils import ILSTestScript


class TestMessageInitiator(ILSTestScript):

    def test_message_initiator_help(self):
        with localize('sw'):
            response = unicode(TEST_HANDLER_HELP)
        script = """
            5551234 > test
            5551234 < %s
        """ % response
        self.run_script(script)

    def test_message_initiator_losses_adjustments(self):
        with localize('sw'):
            response1 = unicode(TEST_HANDLER_CONFIRM)
            response2 = unicode(LOSS_ADJUST_HELP)
        script = """
            5551234 > test la d31049
            5551234 < %(test_handler_confirm)s
            32347 < %(response)s
            32348 < %(response)s
            32349 < %(response)s
            """ % {
            "test_handler_confirm": response1,
            "response": response2
        }
        self.run_script(script)
        supply_point_status = SupplyPointStatus.objects.filter(
            location_id=self.facility3.get_id,
            status_type=SupplyPointStatusTypes.LOSS_ADJUSTMENT_FACILITY
        ).order_by("-status_date")[0]
        self.assertEqual(SupplyPointStatusValues.REMINDER_SENT, supply_point_status.status_value)
        self.assertEqual(SupplyPointStatusTypes.LOSS_ADJUSTMENT_FACILITY, supply_point_status.status_type)

    def test_message_initiator_fw(self):
        with localize('sw'):
            response = unicode(TEST_HANDLER_CONFIRM)
        script = """
            5551234 > test fw D31049 %(test_message)s
            5551234 < %(test_handler_confirm)s
            32347 < %(test_message)s
            32348 < %(test_message)s
            32349 < %(test_message)s
            """ % {"test_handler_confirm": response,
                   "test_message": "this is a test message"}
        self.run_script(script)

    def test_message_initiator_bad_code(self):
        with localize('sw'):
            response = unicode(TEST_HANDLER_BAD_CODE)
        script = """
            5551234 > test la d5000000
            5551234 < %(test_bad_code)s
            """ % {"test_bad_code": response % {"code": "d5000000"}}
        self.run_script(script)

    def test_message_initiator_randr_facility(self):
        with localize('sw'):
            response1 = unicode(TEST_HANDLER_CONFIRM)
            response2 = unicode(SUBMITTED_REMINDER_FACILITY)
        script = """
            5551234 > test randr d31049
            5551234 < %(test_handler_confirm)s
            32347 < %(response)s
            32348 < %(response)s
            32349 < %(response)s
            """ % {
            "test_handler_confirm": response1,
            "response": response2
        }
        self.run_script(script)
        supply_point_status = SupplyPointStatus.objects.filter(
            location_id=self.facility3.get_id,
            status_type=SupplyPointStatusTypes.R_AND_R_FACILITY
        ).order_by("-status_date")[0]
        self.assertEqual(SupplyPointStatusValues.REMINDER_SENT, supply_point_status.status_value)
        self.assertEqual(SupplyPointStatusTypes.R_AND_R_FACILITY, supply_point_status.status_type)

    def test_message_initiator_randr_district(self):
        with localize('sw'):
            response1 = unicode(TEST_HANDLER_CONFIRM)
            response2 = unicode(SUBMITTED_REMINDER_DISTRICT)
        script = """
            5551234 > test randr d10101
            5551234 < %(test_handler_confirm)s
            32350 < %(response)s
            32351 < %(response)s
            32352 < %(response)s
            """ % {
            "test_handler_confirm": response1,
            "response": response2
        }
        self.run_script(script)
        supply_point_status = SupplyPointStatus.objects.filter(
            location_id=self.district2.get_id,
            status_type=SupplyPointStatusTypes.R_AND_R_DISTRICT
        ).order_by("-status_date")[0]
        self.assertEqual(SupplyPointStatusValues.REMINDER_SENT, supply_point_status.status_value)
        self.assertEqual(SupplyPointStatusTypes.R_AND_R_DISTRICT, supply_point_status.status_type)

    def test_message_initiator_delivery_facility(self):
        with localize('sw'):
            response1 = unicode(TEST_HANDLER_CONFIRM)
            response2 = unicode(DELIVERY_REMINDER_FACILITY)
        script = """
            5551234 > test delivery d31049
            5551234 < %(test_handler_confirm)s
            32347 < %(response)s
            32348 < %(response)s
            32349 < %(response)s
            """ % {
            "test_handler_confirm": response1,
            "response": response2
        }
        self.run_script(script)
        supply_point_status = SupplyPointStatus.objects.filter(
            location_id=self.facility3.get_id,
            status_type=SupplyPointStatusTypes.DELIVERY_FACILITY
        ).order_by("-status_date")[0]
        self.assertEqual(SupplyPointStatusValues.REMINDER_SENT, supply_point_status.status_value)
        self.assertEqual(SupplyPointStatusTypes.DELIVERY_FACILITY, supply_point_status.status_type)

    def test_message_initiator_delivery_district(self):
        with localize('sw'):
            response1 = unicode(TEST_HANDLER_CONFIRM)
            response2 = unicode(DELIVERY_REMINDER_DISTRICT)
        script = """
            5551234 > test delivery d10101
            5551234 < %(test_handler_confirm)s
            32350 < %(response)s
            32351 < %(response)s
            32352 < %(response)s
            """ % {
            "test_handler_confirm": response1,
            "response": response2
        }
        self.run_script(script)
        supply_point_status = SupplyPointStatus.objects.filter(
            location_id=self.district2.get_id,
            status_type=SupplyPointStatusTypes.DELIVERY_DISTRICT
        ).order_by("-status_date")[0]
        self.assertEqual(SupplyPointStatusValues.REMINDER_SENT, supply_point_status.status_value)
        self.assertEqual(SupplyPointStatusTypes.DELIVERY_DISTRICT, supply_point_status.status_type)

    def test_message_initiator_late_delivery_report_district(self):
        with localize('sw'):
            response1 = unicode(TEST_HANDLER_CONFIRM)
            response2 = unicode(DELIVERY_LATE_DISTRICT)
        script = """
            5551234 > test latedelivery d10101
            5551234 < %(test_handler_confirm)s
            32350 < %(response)s
            32351 < %(response)s
            32352 < %(response)s
            """ % {
            "test_handler_confirm": response1,
            "response": unicode(response2 % {
                'group_name': 'changeme',
                'group_total': 1,
                'not_responded_count': 2,
                'not_received_count': 3
            })
        }
        self.run_script(script)

    def test_message_initiator_soh(self):
        with localize('sw'):
            response1 = unicode(TEST_HANDLER_CONFIRM)
            response2 = unicode(SOH_HELP_MESSAGE)
        script = """
            5551234 > test soh d31049
            5551234 < %(test_handler_confirm)s
            32347 < %(response)s
            32348 < %(response)s
            32349 < %(response)s
            5551234 > test hmk d31049
            5551234 < %(test_handler_confirm)s
            32347 < %(response)s
            32348 < %(response)s
            32349 < %(response)s
            """ % {
            "test_handler_confirm": response1,
            "response": response2
        }
        self.run_script(script)
        supply_point_status = SupplyPointStatus.objects.filter(
            location_id=self.facility3.get_id,
            status_type=SupplyPointStatusTypes.SOH_FACILITY
        ).order_by("-status_date")[0]
        self.assertEqual(SupplyPointStatusValues.REMINDER_SENT, supply_point_status.status_value)
        self.assertEqual(SupplyPointStatusTypes.SOH_FACILITY, supply_point_status.status_type)

    def test_message_initiator_supervision(self):
        with localize('sw'):
            response1 = unicode(TEST_HANDLER_CONFIRM)
            response2 = unicode(SUPERVISION_REMINDER)
        script = """
            5551234 > test supervision d31049
            5551234 < %(test_handler_confirm)s
            32347 < %(response)s
            32348 < %(response)s
            32349 < %(response)s
            """ % {
            "test_handler_confirm": response1,
            "response": response2
        }
        self.run_script(script)
        supply_point_status = SupplyPointStatus.objects.filter(
            location_id=self.facility3.get_id,
            status_type=SupplyPointStatusTypes.SUPERVISION_FACILITY
        ).order_by("-status_date")[0]
        self.assertEqual(SupplyPointStatusValues.REMINDER_SENT, supply_point_status.status_value)
        self.assertEqual(SupplyPointStatusTypes.SUPERVISION_FACILITY, supply_point_status.status_type)

    def test_message_initiator_soh_thank_you(self):
        with localize('sw'):
            response1 = unicode(TEST_HANDLER_CONFIRM)
            response2 = unicode(SOH_THANK_YOU)
        script = """
            5551234 > test soh_thank_you d31049
            5551234 < %(test_handler_confirm)s
            32347 < %(response)s
            32348 < %(response)s
            32349 < %(response)s
            """ % {
            "test_handler_confirm": response1,
            "response": response2
        }
        self.run_script(script)
