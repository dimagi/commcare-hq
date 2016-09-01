from corehq.toggles import EMG_AND_REC_SMS_HANDLERS, NAMESPACE_DOMAIN
from custom.ilsgateway.tanzania.reminders import EMG_ERROR, EMG_HELP, INVALID_PRODUCT_CODE
from custom.ilsgateway.tests.handlers.utils import ILSTestScript
from custom.zipline.models import EmergencyOrder


class EmergencyTest(ILSTestScript):

    @classmethod
    def setUpClass(cls):
        super(EmergencyTest, cls).setUpClass()
        EMG_AND_REC_SMS_HANDLERS.set('ils-test-domain', True, namespace=NAMESPACE_DOMAIN)

    def tearDown(self):
        EmergencyOrder.objects.all().delete()
        super(EmergencyTest, self).tearDown()

    def test_help(self):
        script = """
            5551234 > emg
            5551234 < {}
        """.format(unicode(EMG_HELP))
        self.run_script(script)

    def test_valid_message(self):
        script = """
            5551234 > emg dp 100 fs 50
        """
        self.run_script(script)

        emergency_order = EmergencyOrder.objects.filter(domain=self.domain.name)[0]

        self.assertListEqual(
            [
                emergency_order.domain,
                emergency_order.requesting_user_id,
                emergency_order.requesting_phone_number,
                emergency_order.location_code,
                emergency_order.products_requested
            ],
            [
                self.domain.name,
                self.user1.get_id,
                '5551234',
                self.user1.sql_location.site_code,
                {'dp': {'quantity': u'100'}, 'fs': {'quantity': u'50'}}
            ]
        )

    def test_invalid_quantity(self):
        script = """
            5551234 > emg dp quantity fs 50
            5551234 < {}
        """.format(unicode(EMG_ERROR))
        self.run_script(script)

    def test_incomplete_message(self):
        script = """
            5551234 > emg dp fs 50
            5551234 < {}
        """.format(unicode(EMG_ERROR))
        self.run_script(script)

    def test_invalid_product_code(self):
        script = """
            5551234 > emg invalid_code 40 fs 50
            5551234 < {}
        """.format(unicode(INVALID_PRODUCT_CODE % {'product_code': 'invalid_code'}))
        self.run_script(script)
