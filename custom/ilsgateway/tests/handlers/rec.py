from __future__ import absolute_import
from datetime import datetime

from corehq.toggles import EMG_AND_REC_SMS_HANDLERS, NAMESPACE_DOMAIN
from custom.ilsgateway.tanzania.reminders import REC_HELP, REC_CONFIRMATION, REC_ERROR, INVALID_PRODUCT_CODE
from custom.ilsgateway.tests.handlers.utils import ILSTestScript, TEST_DOMAIN
from custom.zipline.api import ProductQuantity
from custom.zipline.models import EmergencyOrder, update_product_quantity_json_field, EmergencyOrderStatusUpdate
import six


class ReceiptTest(ILSTestScript):

    @classmethod
    def setUpClass(cls):
        super(ReceiptTest, cls).setUpClass()
        EMG_AND_REC_SMS_HANDLERS.set('ils-test-domain', True, namespace=NAMESPACE_DOMAIN)
        cls.order = EmergencyOrder(
            domain=TEST_DOMAIN,
            requesting_user_id=cls.user1.get_id,
            requesting_phone_number='5551234',
            location=cls.user1.sql_location,
            location_code=cls.user1.sql_location.site_code,
            timestamp=datetime.utcnow()
        )
        update_product_quantity_json_field(
            cls.order.products_requested, [ProductQuantity('dp', 100), ProductQuantity('fs', 50)]
        )
        cls.order.save()

    @classmethod
    def tearDownClass(cls):
        EmergencyOrder.objects.update(confirmed_status=None)
        EmergencyOrderStatusUpdate.objects.all().delete()
        EmergencyOrder.objects.all().delete()
        super(ReceiptTest, cls).tearDownClass()

    def test_help(self):
        script = """
            5551234 > rec
            5551234 < {}
        """.format(six.text_type(REC_HELP))
        self.run_script(script)

    def test_valid_message(self):
        script = """
            5551234 > rec dp 100 fs 50
            5551234 < {}
        """.format(six.text_type(REC_CONFIRMATION))
        self.run_script(script)

        order = EmergencyOrder.objects.get(pk=self.order.pk)
        self.assertDictEqual(
            order.confirmed_status.products,
            {'dp': {'quantity': u'100'}, 'fs': {'quantity': u'50'}}
        )

    def test_invalid_quantity(self):
        script = """
            5551234 > rec dp quantity fs 50
            5551234 < {}
        """.format(six.text_type(REC_ERROR))
        self.run_script(script)

    def test_incomplete_message(self):
        script = """
            5551234 > rec dp fs 50
            5551234 < {}
        """.format(six.text_type(REC_ERROR))
        self.run_script(script)

    def test_invalid_product_code(self):
        script = """
            5551234 > rec invalid_code 40 fs 50
            5551234 < {}
        """.format(six.text_type(INVALID_PRODUCT_CODE % {'product_code': 'invalid_code'}))
        self.run_script(script)
