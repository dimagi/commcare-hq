from datetime import datetime
from django.test.testcases import TestCase
from casexml.apps.stock.models import StockReport
from corehq.apps.commtrack.models import StockState
from corehq.apps.commtrack.tests.util import TEST_BACKEND
from corehq.apps.products.models import Product
from corehq.apps.sms.models import SMS
from custom.ewsghana.alerts import ONGOING_NON_REPORTING, ONGOING_STOCKOUT_AT_SDP, ONGOING_STOCKOUT_AT_RMS
from custom.ewsghana.alerts.ongoing_non_reporting import OnGoingNonReporting
from custom.ewsghana.alerts.ongoing_stockouts import OnGoingStockouts, OnGoingStockoutsRMS
from custom.ewsghana.tests.test_reminders import create_stock_report
from custom.ewsghana.utils import prepare_domain, bootstrap_user, make_loc, assign_products_to_location
from corehq.apps.sms.backend import test


TEST_DOMAIN = 'ewsghana-alerts-test'


class TestAlerts(TestCase):

    @classmethod
    def setUpClass(cls):
        cls.domain = prepare_domain(TEST_DOMAIN)
        test.bootstrap(TEST_BACKEND, to_console=True)
        cls.national = make_loc(code='national', name='National', type='country', domain=TEST_DOMAIN)
        cls.region = make_loc(code="region", name="Test Region", type="region", domain=TEST_DOMAIN,
                              parent=cls.national)
        cls.rms = make_loc(code="rms", name="Test Medical Store", type="Regional Medical Store",
                           domain=TEST_DOMAIN, parent=cls.region)
        cls.rms2 = make_loc(code="rms2", name="Test Medical Store 2", type="Regional Medical Store",
                            domain=TEST_DOMAIN, parent=cls.region)
        cls.district = make_loc(code="district", name="Test District", type="district", domain=TEST_DOMAIN)
        cls.loc1 = make_loc(code="tf", name="Test Facility", type="Hospital", domain=TEST_DOMAIN,
                            parent=cls.district)
        cls.loc2 = make_loc(code="tf2", name="Test Facility 2", type="Hospital", domain=TEST_DOMAIN,
                            parent=cls.district)

        cls.user1 = bootstrap_user(
            username='test1', phone_number='1111', home_loc=cls.district, domain=TEST_DOMAIN,
            first_name='test', last_name='test1',
            user_data={
                'role': []
            }
        )

        cls.national_user = bootstrap_user(
            username='test2', phone_number='2222', home_loc=cls.national, domain=TEST_DOMAIN,
            first_name='test', last_name='test2',
            user_data={
                'role': []
            }
        )

        cls.regional_user = bootstrap_user(
            username='test4', phone_number='4444', home_loc=cls.region, domain=TEST_DOMAIN,
            first_name='test', last_name='test4',
            user_data={
                'role': []
            }
        )

        cls.product = Product(domain=TEST_DOMAIN, name='Test Product', code_='tp', unit='each')
        cls.product.save()

        cls.product2 = Product(domain=TEST_DOMAIN, name='Test Product2', code_='tp2', unit='each')
        cls.product2.save()

        assign_products_to_location(cls.loc1, [cls.product])
        assign_products_to_location(cls.loc2, [cls.product, cls.product2])
        assign_products_to_location(cls.rms, [cls.product, cls.product2])

    def tearDown(self):
        SMS.objects.all().delete()
        StockReport.objects.all().delete()
        StockState.objects.all().delete()

    def test_ongoing_non_reporting(self):
        OnGoingNonReporting(TEST_DOMAIN).send()
        self.assertEqual(SMS.objects.count(), 1)

        smses = SMS.objects.all()
        self.assertEqual(smses[0].text, ONGOING_NON_REPORTING % 'Test Facility, Test Facility 2')

        create_stock_report(self.loc1, {'tp': 1})
        now = datetime.utcnow()

        OnGoingNonReporting(TEST_DOMAIN).send()
        smses = SMS.objects.filter(date__gte=now)
        self.assertEqual(smses.count(), 1)
        self.assertEqual(smses[0].text, ONGOING_NON_REPORTING % 'Test Facility 2')

        create_stock_report(self.loc2, {'tp2': 1})

        now = datetime.utcnow()

        OnGoingNonReporting(TEST_DOMAIN).send()
        smses = SMS.objects.filter(date__gte=now)
        self.assertEqual(smses.count(), 0)

    def test_ongoing_stockouts(self):
        OnGoingStockouts(TEST_DOMAIN).send()

        self.assertEqual(SMS.objects.count(), 0)

        create_stock_report(self.loc1, {'tp': 0})

        now = datetime.utcnow()

        OnGoingStockouts(TEST_DOMAIN).send()
        smses = SMS.objects.filter(date__gte=now)

        self.assertEqual(smses.count(), 1)
        self.assertEqual(smses[0].text, ONGOING_STOCKOUT_AT_SDP % 'Test Facility')

        create_stock_report(self.loc2, {'tp': 0})

        now = datetime.utcnow()

        OnGoingStockouts(TEST_DOMAIN).send()
        smses = SMS.objects.filter(date__gte=now)

        self.assertEqual(smses.count(), 1)
        self.assertEqual(smses[0].text, ONGOING_STOCKOUT_AT_SDP % 'Test Facility, Test Facility 2')

        create_stock_report(self.loc1, {'tp': 10})
        create_stock_report(self.loc2, {'tp': 10})

        now = datetime.utcnow()

        OnGoingStockouts(TEST_DOMAIN).send()
        smses = SMS.objects.filter(date__gte=now)
        self.assertEqual(smses.count(), 0)

    def test_ongoing_stockouts_rms(self):
        OnGoingStockoutsRMS(TEST_DOMAIN).send()

        self.assertEqual(SMS.objects.count(), 0)

        create_stock_report(self.rms, {'tp': 0})
        create_stock_report(self.rms2, {'tp': 0})

        now = datetime.utcnow()
        OnGoingStockoutsRMS(TEST_DOMAIN).send()
        smses = SMS.objects.filter(date__gte=now)

        self.assertEqual(smses.count(), 2)
        self.assertEqual(smses[0].text, ONGOING_STOCKOUT_AT_RMS % 'Test Medical Store, Test Medical Store 2')

        create_stock_report(self.rms2, {'tp': 15})
        now = datetime.utcnow()
        OnGoingStockoutsRMS(TEST_DOMAIN).send()
        smses = SMS.objects.filter(date__gte=now)

        self.assertEqual(smses.count(), 2)
        self.assertEqual(smses[0].text, ONGOING_STOCKOUT_AT_RMS % 'Test Medical Store')

        create_stock_report(self.rms, {'tp': 15})
        now = datetime.utcnow()
        OnGoingStockoutsRMS(TEST_DOMAIN).send()
        smses = SMS.objects.filter(date__gte=now)

        self.assertEqual(smses.count(), 0)
