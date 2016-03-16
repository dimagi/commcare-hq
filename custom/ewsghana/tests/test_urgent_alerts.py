from datetime import datetime

from casexml.apps.stock.models import StockReport

from corehq.apps.commtrack.models import StockState
from corehq.apps.products.models import Product
from corehq.apps.sms.mixin import VerifiedNumber
from corehq.apps.sms.models import SMS
from corehq.apps.sms.tests.util import setup_default_sms_test_backend

from custom.ewsghana.alerts import URGENT_STOCKOUT, URGENT_NON_REPORTING
from custom.ewsghana.alerts.urgent_alerts import UrgentStockoutAlert, UrgentNonReporting
from custom.ewsghana.tests.handlers.utils import EWSTestCase
from custom.ewsghana.tests.test_reminders import create_stock_report
from custom.ewsghana.utils import (
    bootstrap_web_user,
    make_loc,
    prepare_domain,
    set_sms_notifications,
)

TEST_DOMAIN = 'ewsghana-urgent-alerts'


class TestUrgentAlerts(EWSTestCase):

    @classmethod
    def setUpClass(cls):
        cls.backend, cls.sms_backend_mapping = setup_default_sms_test_backend()
        cls.domain = prepare_domain(TEST_DOMAIN)
        cls.district = make_loc(code="district", name="Test District", type="district", domain=TEST_DOMAIN)
        cls.loc1 = make_loc(code="tf", name="Test Facility", type="Hospital", domain=TEST_DOMAIN,
                            parent=cls.district)
        cls.loc2 = make_loc(code="tf2", name="Test Facility 2", type="Hospital", domain=TEST_DOMAIN,
                            parent=cls.district)
        cls.loc3 = make_loc(code="tf3", name="Test Facility 3", type="Hospital", domain=TEST_DOMAIN,
                            parent=cls.district)
        cls.loc4 = make_loc(code="tf4", name="Test Facility 4", type="Hospital", domain=TEST_DOMAIN,
                            parent=cls.district)

        cls.product = Product(domain=TEST_DOMAIN, name='Test Product', code_='tp', unit='each')
        cls.product.save()

        cls.product2 = Product(domain=TEST_DOMAIN, name='Test Product2', code_='tp2', unit='each')
        cls.product2.save()

        cls.user1 = bootstrap_web_user(
            username='test1', phone_number='1111', location=cls.district, domain=TEST_DOMAIN,
            first_name='test', last_name='test1',
            user_data={
                'role': []
            }, email='test1@example.com', password='dummy'
        )

        set_sms_notifications(TEST_DOMAIN, cls.user1, True)

    def tearDown(self):
        SMS.objects.all().delete()
        StockReport.objects.all().delete()
        StockState.objects.all().delete()

    def test_get_products_function(self):
        urgent_stockout_alert = UrgentStockoutAlert(TEST_DOMAIN)
        self.assertEqual(len(urgent_stockout_alert.get_sql_products_list(self.district.sql_location)), 0)
        create_stock_report(self.loc1, {'tp': 0})
        self.assertEqual(len(urgent_stockout_alert.get_sql_products_list(self.district.sql_location)), 0)
        create_stock_report(self.loc2, {'tp': 0})
        self.assertEqual(len(urgent_stockout_alert.get_sql_products_list(self.district.sql_location)), 0)
        create_stock_report(self.loc3, {'tp': 0})
        self.assertEqual(len(urgent_stockout_alert.get_sql_products_list(self.district.sql_location)), 1)

        create_stock_report(self.loc1, {'tp2': 0})
        create_stock_report(self.loc2, {'tp2': 0})
        create_stock_report(self.loc3, {'tp2': 0})
        self.assertEqual(len(urgent_stockout_alert.get_sql_products_list(self.district.sql_location)), 2)

    def test_urgent_stockout_alert(self):
        urgent_stockout_alert = UrgentStockoutAlert(TEST_DOMAIN)
        urgent_stockout_alert.send()
        self.assertEqual(SMS.objects.count(), 0)

        create_stock_report(self.loc1, {'tp2': 0})
        create_stock_report(self.loc2, {'tp2': 0})
        create_stock_report(self.loc3, {'tp2': 0})

        urgent_stockout_alert.send()
        self.assertEqual(SMS.objects.count(), 1)
        self.assertEqual(SMS.objects.all().first().text, URGENT_STOCKOUT % {
            'location': self.district.name,
            'products': "Test Product2",
        })

        create_stock_report(self.loc1, {'tp': 0})
        create_stock_report(self.loc2, {'tp': 0})
        create_stock_report(self.loc3, {'tp': 0})

        now = datetime.utcnow()
        urgent_stockout_alert.send()
        smses = SMS.objects.filter(date__gte=now)
        self.assertEqual(smses.count(), 1)
        self.assertEqual(smses.first().text, URGENT_STOCKOUT % {
            'location': self.district.name,
            'products': "Test Product, Test Product2",
        })

    def test_urgent_non_reporting_alert(self):
        urgent_non_reporting = UrgentNonReporting(TEST_DOMAIN)
        urgent_non_reporting.send()
        self.assertEqual(SMS.objects.count(), 1)
        self.assertEqual(SMS.objects.all().first().text, URGENT_NON_REPORTING % self.district.name)

        create_stock_report(self.loc1, {'tp2': 0})
        create_stock_report(self.loc2, {'tp2': 0})
        now = datetime.utcnow()
        self.assertEqual(SMS.objects.filter(date__gte=now).count(), 0)

    @classmethod
    def tearDownClass(cls):
        cls.user1.delete()
        for vn in VerifiedNumber.by_domain(TEST_DOMAIN):
            vn.delete()
        super(TestUrgentAlerts, cls).tearDownClass()
