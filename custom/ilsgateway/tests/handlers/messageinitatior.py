from custom.ilsgateway.tanzania.reminders import TEST_HANDLER_CONFIRM, SUBMITTED_REMINDER_FACILITY, \
    LOSS_ADJUST_HELP, TEST_HANDLER_BAD_CODE, DELIVERY_REMINDER_FACILITY, SOH_HELP_MESSAGE, SUPERVISION_REMINDER, \
    SOH_THANK_YOU, SUBMITTED_REMINDER_DISTRICT, DELIVERY_REMINDER_DISTRICT, DELIVERY_LATE_DISTRICT
from custom.ilsgateway.tests.handlers.utils import ILSTestScript


class TestMessageInitiatior(ILSTestScript):

    def test_message_initatior_losses_adjustments(self):
        script = """
            5551234 > test la d31049
            5551234 < %(test_handler_confirm)s
            32347 < %(response)s
            32348 < %(response)s
            32349 < %(response)s
            """ % {
            "test_handler_confirm": unicode(TEST_HANDLER_CONFIRM),
            "response": unicode(LOSS_ADJUST_HELP)
        }
        self.run_script(script)

    def test_message_initatior_fw(self):
        script = """
            5551234 > test fw D31049 %(test_message)s
            5551234 < %(test_handler_confirm)s
            32347 < %(test_message)s
            32348 < %(test_message)s
            32349 < %(test_message)s
            """ % {"test_handler_confirm": unicode(TEST_HANDLER_CONFIRM),
                   "test_message": "this is a test message"}
        self.run_script(script)
        
    def test_message_initiator_bad_code(self):
        script = """
            5551234 > test la d5000000
            5551234 < %(test_bad_code)s
            """ % {"test_bad_code": unicode(TEST_HANDLER_BAD_CODE % {"code": "d5000000"})}
        self.run_script(script)

    def test_message_initatior_randr_facility(self):
        script = """
            5551234 > test randr d31049
            5551234 < %(test_handler_confirm)s
            32347 < %(response)s
            32348 < %(response)s
            32349 < %(response)s
            """ % {
            "test_handler_confirm": unicode(TEST_HANDLER_CONFIRM),
            "response": unicode(SUBMITTED_REMINDER_FACILITY)
        }
        self.run_script(script)

    def test_message_initatior_randr_district(self):
        script = """
            5551234 > test randr d10101
            5551234 < %(test_handler_confirm)s
            32350 < %(response)s
            32351 < %(response)s
            32352 < %(response)s
            """ % {
            "test_handler_confirm": unicode(TEST_HANDLER_CONFIRM),
            "response": unicode(SUBMITTED_REMINDER_DISTRICT)
        }
        self.run_script(script)

    def test_message_initatior_delivery_facility(self):
        script = """
            5551234 > test delivery d31049
            5551234 < %(test_handler_confirm)s
            32347 < %(response)s
            32348 < %(response)s
            32349 < %(response)s
            """ % {
            "test_handler_confirm": unicode(TEST_HANDLER_CONFIRM),
            "response": unicode(DELIVERY_REMINDER_FACILITY)
        }
        self.run_script(script)

    def test_message_initatior_delivery_district(self):
        script = """
            5551234 > test delivery d10101
            5551234 < %(test_handler_confirm)s
            32350 < %(response)s
            32351 < %(response)s
            32352 < %(response)s
            """ % {
            "test_handler_confirm": unicode(TEST_HANDLER_CONFIRM),
            "response": unicode(DELIVERY_REMINDER_DISTRICT)
        }
        self.run_script(script)

    def test_message_initiator_delivery_report_district(self):
        script = """
            5551234 > test latedelivery d10101
            5551234 < %(test_handler_confirm)s
            32350 < %(response)s
            32351 < %(response)s
            32352 < %(response)s
            """ % {
            "test_handler_confirm": unicode(TEST_HANDLER_CONFIRM),
            "response": unicode(DELIVERY_LATE_DISTRICT % {
                'group_name': 'changeme',
                'group_total': 1,
                'not_responded_count': 2,
                'not_received_count': 3
            })
        }
        self.run_script(script)

    def test_message_initatior_soh(self):
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
            "test_handler_confirm": unicode(TEST_HANDLER_CONFIRM),
            "response": unicode(SOH_HELP_MESSAGE)
        }
        self.run_script(script)

    def test_message_initatior_supervision(self):
        script = """
            5551234 > test supervision d31049
            5551234 < %(test_handler_confirm)s
            32347 < %(response)s
            32348 < %(response)s
            32349 < %(response)s
            """ % {
            "test_handler_confirm": unicode(TEST_HANDLER_CONFIRM),
            "response": unicode(SUPERVISION_REMINDER)
        }
        self.run_script(script)

    def test_message_initatior_soh_thank_you(self):
        script = """
            5551234 > test soh_thank_you d31049
            5551234 < %(test_handler_confirm)s
            32347 < %(response)s
            32348 < %(response)s
            32349 < %(response)s
            """ % {
            "test_handler_confirm": unicode(TEST_HANDLER_CONFIRM),
            "response": unicode(SOH_THANK_YOU)
        }
        self.run_script(script)