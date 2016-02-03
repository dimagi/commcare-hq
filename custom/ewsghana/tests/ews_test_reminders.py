from django.test import TestCase
from corehq.apps.products.models import Product, SQLProduct
from corehq.apps.sms.tests.util import setup_default_sms_test_backend
from custom.ewsghana.tests.test_reminders import create_stock_report
from custom.ewsghana.utils import prepare_domain, make_loc, report_status, \
    assign_products_to_location


TEST_DOMAIN = 'ews-reminders-test'


class EWSTestReminders(TestCase):
    """Moved from EWS"""

    @classmethod
    def setUpClass(cls):
        cls.backend, cls.sms_backend_mapping = setup_default_sms_test_backend()
        cls.domain = prepare_domain(TEST_DOMAIN)

    def setUp(self):
        self.facility = make_loc('test-faciity', 'Test Facility', TEST_DOMAIN, 'Polyclinic')
        self.commodity = Product(domain=TEST_DOMAIN, name='Drug A', code_='ab', unit='cycle')
        self.commodity.save()

        self.commodity2 = Product(domain=TEST_DOMAIN, name='Drug B', code_='cd', unit='cycle')
        self.commodity2.save()

        self.sql_facility = self.facility.sql_location
        self.sql_facility.products = []
        self.sql_facility.save()

    def test_reminders(self):
        products_reported, products_not_reported = report_status(self.facility.sql_location, days_until_late=1)
        self.assertEqual(len(products_reported), 0)
        self.assertEqual(len(products_not_reported), 0)

        assign_products_to_location(self.facility, [self.commodity])
        products_reported, products_not_reported = report_status(self.facility.sql_location, days_until_late=1)
        self.assertEqual(len(products_reported), 0)

        sql_commodity = SQLProduct.objects.get(product_id=self.commodity.get_id)
        self.assertEqual(products_not_reported[0], sql_commodity)

        sql_commodity2 = SQLProduct.objects.get(product_id=self.commodity2.get_id)

        create_stock_report(self.facility, {'ab': 10})
        products_reported, products_not_reported = report_status(self.facility.sql_location, days_until_late=1)
        self.assertEqual(products_reported[0], sql_commodity)
        self.assertEqual(len(products_not_reported), 0)

        assign_products_to_location(self.facility, [self.commodity, self.commodity2])
        products_reported, products_not_reported = report_status(self.facility.sql_location, days_until_late=1)
        self.assertEqual(products_reported[0], sql_commodity)
        self.assertEqual(products_not_reported[0], sql_commodity2)

        create_stock_report(self.facility, {'cd': 10})
        products_reported, products_not_reported = report_status(self.facility.sql_location, days_until_late=1)
        self.assertTrue(sql_commodity in products_reported)
        self.assertTrue(sql_commodity2 in products_reported)
        self.assertEqual(len(products_not_reported), 0)

    @classmethod
    def tearDownClass(cls):
        cls.sms_backend_mapping.delete()
        cls.backend.delete()
