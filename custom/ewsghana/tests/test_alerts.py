from datetime import datetime

from casexml.apps.stock.models import StockReport

from corehq.apps.commtrack.models import StockState
from corehq.apps.products.models import Product
from corehq.apps.sms.mixin import VerifiedNumber
from corehq.apps.sms.models import SMS
from corehq.apps.sms.tests.util import setup_default_sms_test_backend

from custom.ewsghana.alerts import ONGOING_NON_REPORTING, ONGOING_STOCKOUT_AT_SDP, ONGOING_STOCKOUT_AT_RMS
from custom.ewsghana.tasks import on_going_non_reporting, on_going_stockout
from custom.ewsghana.tests.handlers.utils import EWSTestCase
from custom.ewsghana.tests.test_reminders import create_stock_report
from custom.ewsghana.utils import (
    assign_products_to_location,
    bootstrap_web_user,
    make_loc,
    prepare_domain,
    set_sms_notifications,
)

TEST_DOMAIN = 'ewsghana-alerts-test'


class TestAlerts(EWSTestCase):

    @classmethod
    def setUpClass(cls):
        cls.backend, cls.sms_backend_mapping = setup_default_sms_test_backend()
        cls.domain = prepare_domain(TEST_DOMAIN)

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

        cls.user1 = bootstrap_web_user(
            username='test1', phone_number='1111', location=cls.district, domain=TEST_DOMAIN,
            first_name='test', last_name='test1',
            user_data={
                'role': []
            }, email='test1@example.com', password='dummy'
        )

        set_sms_notifications(TEST_DOMAIN, cls.user1, True)

        cls.national_user = bootstrap_web_user(
            username='test2', phone_number='2222', location=cls.national, domain=TEST_DOMAIN,
            first_name='test', last_name='test2',
            user_data={
                'role': []
            }, email='test2@example.com', password='dummy'
        )

        set_sms_notifications(TEST_DOMAIN, cls.national_user, True)

        cls.regional_user = bootstrap_web_user(
            username='test4', phone_number='4444', location=cls.region, domain=TEST_DOMAIN,
            first_name='test', last_name='test4',
            user_data={
                'role': []
            }, email='test4@example.com', password='dummy'
        )

        set_sms_notifications(TEST_DOMAIN, cls.regional_user, True)

        cls.product = Product(domain=TEST_DOMAIN, name='Test Product', code_='tp', unit='each')
        cls.product.save()

        cls.product2 = Product(domain=TEST_DOMAIN, name='Test Product2', code_='tp2', unit='each')
        cls.product2.save()

        assign_products_to_location(cls.loc1, [cls.product])
        assign_products_to_location(cls.loc2, [cls.product, cls.product2])
        assign_products_to_location(cls.rms, [cls.product, cls.product2])

    @classmethod
    def tearDownClass(cls):
        cls.user1.delete()
        cls.national_user.delete()
        cls.regional_user.delete()
        for vn in VerifiedNumber.by_domain(TEST_DOMAIN):
            vn.delete()
        super(TestAlerts, cls).tearDownClass()

    def tearDown(self):
        SMS.objects.all().delete()
        StockReport.objects.all().delete()
        StockState.objects.all().delete()

    def test_ongoing_non_reporting(self):
        now = datetime.utcnow()
        on_going_non_reporting()
        self.assertEqual(SMS.objects.count(), 1)

        smses = SMS.objects.all()
        self.assertEqual(smses[0].text, ONGOING_NON_REPORTING % 'Test Facility, Test Facility 2')

        on_going_non_reporting()
        # Shouldn't be send again
        self.assertEqual(SMS.objects.filter(date__gte=now).count(), 1)

    def test_ongoing_stockouts(self):
        on_going_stockout()
        self.assertEqual(SMS.objects.count(), 0)

        now = datetime.utcnow()
        create_stock_report(self.loc1, {'tp': 0})

        on_going_stockout()
        smses = SMS.objects.filter(date__gte=now)

        self.assertEqual(smses.count(), 1)
        self.assertEqual(smses[0].text, ONGOING_STOCKOUT_AT_SDP % 'Test Facility')

        on_going_stockout()
        # Shouldn't be send again
        self.assertEqual(SMS.objects.filter(date__gte=now).count(), 1)

    def test_ongoing_stockouts_rms(self):
        on_going_stockout()

        self.assertEqual(SMS.objects.count(), 0)

        create_stock_report(self.rms, {'tp': 0})
        create_stock_report(self.rms2, {'tp': 0})

        now = datetime.utcnow()
        on_going_stockout()
        smses = SMS.objects.filter(date__gte=now)

        self.assertEqual(smses.count(), 2)
        self.assertEqual(smses[0].text, ONGOING_STOCKOUT_AT_RMS % 'Test Medical Store, Test Medical Store 2')

        on_going_stockout()
        # Shouldn't be send again
        self.assertEqual(SMS.objects.filter(date__gte=now).count(), 2)
