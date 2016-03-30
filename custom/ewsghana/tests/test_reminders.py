from datetime import datetime, timedelta
from decimal import Decimal

from casexml.apps.stock.models import StockTransaction, StockReport

from corehq.apps.commtrack.models import StockState
from corehq.apps.locations.tests.util import make_loc
from corehq.apps.products.models import SQLProduct, Product
from corehq.apps.sms.models import SMS
from corehq.apps.sms.tests.util import setup_default_sms_test_backend, delete_domain_phone_numbers

from custom.ewsghana.models import FacilityInCharge, EWSExtension
from custom.ewsghana.reminders import STOCK_ON_HAND_REMINDER, SECOND_STOCK_ON_HAND_REMINDER, \
    SECOND_INCOMPLETE_SOH_REMINDER, STOCKOUT_REPORT, THIRD_STOCK_ON_HAND_REMINDER, INCOMPLETE_SOH_TO_SUPER
from custom.ewsghana.reminders.second_soh_reminder import SecondSOHReminder
from custom.ewsghana.tasks import first_soh_reminder, second_soh_reminder, third_soh_to_super, \
    stockout_notification_to_web_supers, reminder_to_visit_website, reminder_to_submit_rrirv
from custom.ewsghana.tests.handlers.utils import EWSTestCase
from custom.ewsghana.utils import prepare_domain, bootstrap_user, bootstrap_web_user, \
    set_sms_notifications

TEST_DOMAIN = 'ews-reminders-test-domain'


def create_stock_report(location, products_quantities, date=datetime.utcnow()):
    sql_location = location.sql_location
    report = StockReport.objects.create(
        form_id='ews-reminders-test',
        domain=sql_location.domain,
        type='balance',
        date=date
    )
    for product_code, quantity in products_quantities.iteritems():
        StockTransaction(
            stock_on_hand=Decimal(quantity),
            report=report,
            type='stockonhand',
            section_id='stock',
            case_id=sql_location.supply_point_id,
            product_id=SQLProduct.objects.get(domain=sql_location.domain, code=product_code).product_id
        ).save()


class TestReminders(EWSTestCase):

    @classmethod
    def setUpClass(cls):
        cls.backend, cls.sms_backend_mapping = setup_default_sms_test_backend()
        cls.domain = prepare_domain(TEST_DOMAIN)
        cls.loc1 = make_loc(code="garms", name="Test RMS", type="Regional Medical Store", domain=TEST_DOMAIN)
        cls.loc2 = make_loc(code="tf", name="Test Facility", type="Hospital", domain=TEST_DOMAIN)
        cls.region = make_loc(code="region", name="Test Region", type="region", domain=TEST_DOMAIN)

        cls.user1 = bootstrap_user(
            username='test1', phone_number='1111', home_loc=cls.loc2, domain=TEST_DOMAIN,
            first_name='test', last_name='test1',
            user_data={
                'role': []
            }
        )
        cls.user2 = bootstrap_user(
            username='test2', phone_number='2222', home_loc=cls.loc1, domain=TEST_DOMAIN,
            first_name='test', last_name='test2',
            user_data={
                'role': ['Other'],
                'needs_reminders': "False"
            }
        )

        cls.user3 = bootstrap_user(
            username='test3', phone_number='3333', home_loc=cls.loc2, domain=TEST_DOMAIN,
            first_name='test', last_name='test3',
            user_data={
                'role': ['Nurse'],
                'needs_reminders': "True"
            }
        )

        cls.in_charge = bootstrap_user(
            username='test4', phone_number='4444', home_loc=cls.loc2, domain=TEST_DOMAIN,
            first_name='test', last_name='test4',
            user_data={
                'role': ['In Charge']
            }
        )

        cls.web_user = bootstrap_web_user(
            domain=TEST_DOMAIN,
            username='testwebuser',
            password='dummy',
            email='test@example.com',
            location=cls.loc2,
            phone_number='5555'
        )

        EWSExtension.objects.create(
            domain=TEST_DOMAIN,
            user_id=cls.web_user.get_id,
            sms_notifications=True,
            location_id=cls.loc2.get_id
        )

        cls.web_user2 = bootstrap_web_user(
            domain=TEST_DOMAIN,
            username='testwebuser2',
            password='dummy',
            email='test2@example.com',
            location=cls.region,
            phone_number='6666'
        )

        set_sms_notifications(TEST_DOMAIN, cls.web_user2, True)

        FacilityInCharge.objects.create(
            user_id=cls.in_charge.get_id,
            location=cls.loc2.sql_location
        )

        cls.product = Product(
            domain=TEST_DOMAIN,
            name='Test Product',
            code_='tp',
            unit='each'
        )
        cls.product.save()

        cls.product2 = Product(
            domain=TEST_DOMAIN,
            name='Test Product2',
            code_='tp2',
            unit='each'
        )
        cls.product2.save()

        sql_product = SQLProduct.objects.get(product_id=cls.product.get_id)
        sql_product2 = SQLProduct.objects.get(product_id=cls.product2.get_id)

        sql_location1 = cls.loc1.sql_location
        sql_location2 = cls.loc2.sql_location

        sql_location1.products = [sql_product]
        sql_location2.products = [sql_product, sql_product2]
        sql_location1.save()
        sql_location2.save()

    def tearDown(self):
        SMS.objects.all().delete()
        StockState.objects.all().delete()
        StockReport.objects.all().delete()

    @classmethod
    def tearDownClass(cls):
        delete_domain_phone_numbers(TEST_DOMAIN)
        cls.user1.delete()
        cls.user2.delete()
        cls.user3.delete()
        cls.domain.delete()
        FacilityInCharge.objects.all().delete()

        super(TestReminders, cls).tearDownClass()

    def test_first_soh_reminder(self):
        first_soh_reminder()
        smses = SMS.objects.all()
        self.assertEqual(smses.count(), 1)

        self.assertEqual(
            smses[0].text,
            STOCK_ON_HAND_REMINDER % {'name': self.user3.full_name}
        )

    def test_second_soh_reminder(self):
        second_soh_reminder()
        smses = SMS.objects.all().order_by('-date')
        self.assertEqual(smses.count(), 2)

        self.assertEqual(
            smses[0].text,
            SECOND_STOCK_ON_HAND_REMINDER % {'name': self.user3.full_name}
        )

        self.assertEqual(
            smses[1].text,
            SECOND_STOCK_ON_HAND_REMINDER % {'name': self.user2.full_name}
        )

        create_stock_report(self.loc1, {
            'tp': 100
        })

        now = datetime.utcnow()
        second_soh_reminder()
        smses = smses.filter(date__gte=now)
        self.assertEqual(smses.count(), 1)

        self.assertEqual(
            smses[0].text,
            SECOND_STOCK_ON_HAND_REMINDER % {'name': self.user3.full_name}
        )

        create_stock_report(self.loc2, {
            'tp': 100
        })
        now = datetime.utcnow()
        second_soh_reminder()
        smses = SMS.objects.filter(date__gte=now)
        self.assertEqual(smses.count(), 1)
        self.assertEqual(
            smses[0].text,
            SECOND_INCOMPLETE_SOH_REMINDER % {'name': self.user3.full_name, 'products': 'Test Product2'}
        )

        create_stock_report(self.loc2, {
            'tp2': 100
        })
        now = datetime.utcnow()
        SecondSOHReminder(TEST_DOMAIN).send()
        smses = SMS.objects.filter(date__gte=now)
        self.assertEqual(smses.count(), 0)

    def test_third_soh_reminder(self):
        third_soh_to_super()
        smses = SMS.objects.all()
        self.assertEqual(smses.count(), 2)

        self.assertEqual(smses[0].text, THIRD_STOCK_ON_HAND_REMINDER % {
            'name': self.web_user2.full_name,
            'facility': self.loc2.name,
        })
        self.assertEqual(smses[1].text, THIRD_STOCK_ON_HAND_REMINDER % {
            'name': self.in_charge.full_name,
            'facility': self.loc2.name,
        })

        create_stock_report(self.loc2, {
            'tp': 100
        })
        now = datetime.utcnow()
        third_soh_to_super()
        smses = SMS.objects.filter(date__gte=now)
        self.assertEqual(smses.count(), 2)
        self.assertEqual(
            smses[0].text,
            INCOMPLETE_SOH_TO_SUPER % {
                'name': self.web_user2.full_name,
                'facility': self.loc2.name,
                'products': 'Test Product2'
            }
        )
        self.assertEqual(
            smses[1].text,
            INCOMPLETE_SOH_TO_SUPER % {
                'name': self.in_charge.full_name,
                'facility': self.loc2.name,
                'products': 'Test Product2'
            }
        )

        create_stock_report(self.loc2, {
            'tp2': 100
        })
        now = datetime.utcnow()
        third_soh_to_super()
        smses = SMS.objects.filter(date__gte=now)
        self.assertEqual(smses.count(), 0)

    def test_stockout_reminder(self):
        stockout_notification_to_web_supers()
        smses = SMS.objects.all()
        self.assertEqual(smses.count(), 0)

        create_stock_report(
            self.loc2, {
                'tp': 0
            }
        )

        stockout_notification_to_web_supers()
        smses = SMS.objects.all()
        self.assertEqual(smses.count(), 1)

        last_modified_date = StockState.objects.latest('last_modified_date').last_modified_date.strftime('%b %d')

        self.assertEqual(
            smses[0].text,
            STOCKOUT_REPORT % {
                'name': self.web_user.full_name,
                'facility': self.loc2.name,
                'products': 'Test Product',
                'date': last_modified_date
            }
        )

        set_sms_notifications(TEST_DOMAIN, self.web_user, False)
        self.web_user.save()

        now = datetime.utcnow()
        stockout_notification_to_web_supers()
        smses = SMS.objects.filter(date__gte=now)
        self.assertEqual(smses.count(), 0)

    def test_rrirv_reminder(self):
        reminder_to_submit_rrirv()

        smses = SMS.objects.all()
        self.assertEqual(smses.count(), 2)

    def test_visit_reminder(self):
        reminder_to_visit_website()
        smses = SMS.objects.all()
        self.assertEqual(smses.count(), 0)
        now = datetime.utcnow()
        self.web_user2.last_login = now - timedelta(weeks=14)
        self.web_user2.save()

        reminder_to_visit_website()

        smses = SMS.objects.filter(date__gte=now)
        self.assertEqual(smses.count(), 1)

        set_sms_notifications(TEST_DOMAIN, self.web_user2, False)
        self.web_user2.save()

        now = datetime.utcnow()
        reminder_to_visit_website()

        smses = SMS.objects.filter(date__gte=now)
        self.assertEqual(smses.count(), 0)
