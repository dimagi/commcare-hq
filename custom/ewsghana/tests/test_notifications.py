from datetime import datetime, timedelta
import mock

from corehq.apps.locations.models import Location
from corehq.apps.products.models import Product
from corehq.apps.programs.models import Program
from corehq.apps.sms.mixin import VerifiedNumber
from corehq.apps.sms.tests.util import setup_default_sms_test_backend
from corehq.apps.users.models import WebUser

from custom.ewsghana.alerts.alert import Notification
from custom.ewsghana.alerts.ongoing_non_reporting import OnGoingNonReporting
from custom.ewsghana.alerts.ongoing_stockouts import OnGoingStockouts
from custom.ewsghana.alerts.urgent_alerts import UrgentStockoutAlert, UrgentNonReporting
from custom.ewsghana.tests.handlers.utils import EWSTestCase
from custom.ewsghana.tests.test_reminders import create_stock_report
from custom.ewsghana.utils import (
    assign_products_to_location,
    bootstrap_web_user,
    make_loc,
    prepare_domain,
    set_sms_notifications,
)


class MissingReportNotificationTestCase(EWSTestCase):
    TEST_DOMAIN = 'notifications-test-ews'

    @classmethod
    def setUpClass(cls):
        cls.backend, cls.sms_backend_mapping = setup_default_sms_test_backend()
        cls.domain = prepare_domain(cls.TEST_DOMAIN)

        cls.program = Program(domain=cls.TEST_DOMAIN, name='Test Program')
        cls.program.save()

        cls.program2 = Program(domain=cls.TEST_DOMAIN, name='Test Program2')
        cls.program2.save()

    def setUp(self):
        self.district = make_loc('test-district', 'Test District', self.TEST_DOMAIN, 'district')
        self.facility = make_loc('test-faciity', 'Test Facility', self.TEST_DOMAIN, 'Polyclinic', self.district)
        self.user = bootstrap_web_user(
            username='test', domain=self.TEST_DOMAIN, phone_number='+4444', location=self.district,
            email='test@example.com', password='dummy', user_data={}
        )
        self.product = Product(domain=self.TEST_DOMAIN, name='Test Product', code_='tp', unit='each')
        self.product.save()

    def tearDown(self):
        for location in Location.by_domain(self.TEST_DOMAIN):
            location.delete()

        for user in WebUser.by_domain(self.TEST_DOMAIN):
            user.delete()

        for vn in VerifiedNumber.by_domain(self.TEST_DOMAIN):
            vn.delete()

        for product in Product.by_domain(self.TEST_DOMAIN):
            product.delete()

    def test_all_facilities_reported(self):
        """No notifications generated if all have reported."""
        create_stock_report(self.facility, {'tp': 5})
        generated = list(OnGoingNonReporting(self.TEST_DOMAIN).get_notifications())
        self.assertEqual(len(generated), 0)

    def test_missing_notification(self):
        """Inspect the generated notifcation for a non-reporting facility."""
        generated = list(OnGoingNonReporting(self.TEST_DOMAIN).get_notifications())
        self.assertEqual(len(generated), 1)

        self.assertEqual(generated[0].user.get_id, self.user.get_id)

    def test_facility_in_district(self):
        """Facility location can be any child of the district."""
        make_loc('test-faciity2', 'Test Facility2', self.TEST_DOMAIN, 'Polyclinic', self.district)
        generated = list(OnGoingNonReporting(self.TEST_DOMAIN).get_notifications())

        self.assertEqual(len(generated), 1)

        self.assertEqual(generated[0].user.get_id, self.user.get_id)

    def test_multiple_users(self):
        """Each user will get their own notification."""
        other_user = bootstrap_web_user(
            username='test2', domain=self.TEST_DOMAIN, phone_number='+44445', location=self.district,
            password='dummy', email='test@example.com', user_data={}
        )

        generated = list(OnGoingNonReporting(self.TEST_DOMAIN).get_notifications())

        self.assertEqual(len(generated), 2)
        self.assertEqual(
            {notification.user.get_id for notification in generated},
            {other_user.get_id, self.user.get_id}
        )

    def test_product_type_filter(self):
        """User can recieve missing notifications for only certain product type."""
        bootstrap_web_user(
            username='test2', domain=self.TEST_DOMAIN, phone_number='+44445', location=self.district,
            password='dummy', email='test@example.com', user_data={}, program_id=self.program.get_id
        )

        other_product = Product(domain=self.TEST_DOMAIN, name='Test Product2', code_='tp2', unit='each')
        other_product2 = Product(domain=self.TEST_DOMAIN, name='Test Product3', code_='tp3', unit='each')
        other_product.save()
        other_product2.save()
        assign_products_to_location(self.facility, [self.product, other_product, other_product2])

        generated = list(OnGoingNonReporting(self.TEST_DOMAIN).get_notifications())

        self.assertEqual(len(generated), 1)
        self.assertEqual(generated[0].user.get_id, self.user.get_id)

    def test_incomplete_with_filter(self):
        """
        User with product type filter will get notification all products of that
        type are missing reports.
        """
        self.user.get_domain_membership(self.TEST_DOMAIN).program_id = self.program.get_id
        self.user.save()

        self.product.program_id = self.program.get_id
        self.product.save()

        create_stock_report(self.facility, {'tp': 100}, date=datetime.utcnow() - timedelta(days=365))

        other_product = Product(
            domain=self.TEST_DOMAIN, name='Test Product2', code_='tp2', unit='each', program_id=self.program.get_id
        )
        other_product.save()
        assign_products_to_location(self.facility, [self.product, other_product])
        generated = list(OnGoingNonReporting(self.TEST_DOMAIN).get_notifications())

        self.assertEqual(len(generated), 1)
        self.assertEqual(generated[0].user.get_id, self.user.get_id)

    def test_incomplete_report(self):
        create_stock_report(self.facility, {'tp': 100}, date=datetime.utcnow())
        self.product.program_id = self.program.get_id
        self.product.save()
        other_product = Product(
            domain=self.TEST_DOMAIN, name='Test Product2', code_='tp2', unit='each', program_id=self.program.get_id
        )
        other_product.save()
        assign_products_to_location(self.facility, [self.product, other_product])
        generated = list(OnGoingNonReporting(self.TEST_DOMAIN).get_notifications())

        self.assertEqual(len(generated), 0)

    def test_incomplete_report2(self):
        create_stock_report(self.facility, {'tp': 100}, date=datetime.utcnow())
        self.product.program_id = self.program2.get_id
        self.product.save()
        other_product = Product(
            domain=self.TEST_DOMAIN, name='Test Product2', code_='tp2', unit='each', program_id=self.program.get_id
        )
        other_product.save()
        assign_products_to_location(self.facility, [self.product, other_product])
        generated = list(OnGoingNonReporting(self.TEST_DOMAIN).get_notifications())

        self.assertEqual(len(generated), 0)


class StockoutReportNotificationTestCase(EWSTestCase):
    TEST_DOMAIN = 'notifications-test-ews2'

    @classmethod
    def setUpClass(cls):
        cls.backend, cls.sms_backend_mapping = setup_default_sms_test_backend()
        cls.domain = prepare_domain(cls.TEST_DOMAIN)
        cls.program = Program(domain=cls.TEST_DOMAIN, name='Test Program')
        cls.program.save()

    def setUp(self):
        self.district = make_loc('test-district', 'Test District', self.TEST_DOMAIN, 'district')
        self.facility = make_loc('test-faciity', 'Test Facility', self.TEST_DOMAIN, 'Polyclinic', self.district)
        self.user = bootstrap_web_user(
            username='test', domain=self.TEST_DOMAIN, phone_number='+4444', location=self.district,
            email='test@example.com', password='dummy', user_data={}
        )
        self.product = Product(domain=self.TEST_DOMAIN, name='Test Product', code_='tp', unit='each')
        self.product.save()

    def tearDown(self):
        for location in Location.by_domain(self.TEST_DOMAIN):
            location.delete()

        for user in WebUser.by_domain(self.TEST_DOMAIN):
            user.delete()

        for vn in VerifiedNumber.by_domain(self.TEST_DOMAIN):
            vn.delete()

        for product in Product.by_domain(self.TEST_DOMAIN):
            product.delete()

    def test_missing_notification(self):
        """No notification if there were no reports. Covered by missing report."""
        generated = list(OnGoingStockouts(self.TEST_DOMAIN).get_notifications())
        self.assertEqual(len(generated), 0)

    def test_all_products_stocked(self):
        """No notification if all products are stocked."""
        assign_products_to_location(self.facility, [self.product])
        create_stock_report(self.facility, {'tp': 10})

        generated = list(OnGoingStockouts(self.TEST_DOMAIN).get_notifications())
        self.assertEqual(len(generated), 0)

    def test_simple_stockout(self):
        """Single product, single report with 0 quantity."""
        assign_products_to_location(self.facility, [self.product])
        create_stock_report(self.facility, {'tp': 0})

        generated = list(OnGoingStockouts(self.TEST_DOMAIN).get_notifications())
        self.assertEqual(len(generated), 1)
        self.assertEqual(generated[0].user.get_id, self.user.get_id)

    def test_multi_report_stockout(self):
        """Single product, mutliple reports with 0 quantity."""
        assign_products_to_location(self.facility, [self.product])
        create_stock_report(self.facility, {'tp': 0})
        create_stock_report(self.facility, {'tp': 0})
        create_stock_report(self.facility, {'tp': 0})

        generated = list(OnGoingStockouts(self.TEST_DOMAIN).get_notifications())
        self.assertEqual(len(generated), 1)
        self.assertEqual(generated[0].user.get_id, self.user.get_id)

    def test_partial_duration_stockout(self):
        """Some reports indicate a stockout but did not last the entire period. No notification."""
        assign_products_to_location(self.facility, [self.product])
        create_stock_report(self.facility, {'tp': 0})
        create_stock_report(self.facility, {'tp': 1})

        generated = list(OnGoingStockouts(self.TEST_DOMAIN).get_notifications())
        self.assertEqual(len(generated), 0)

    def test_partial_product_stockout(self):
        """Multiple products but only one is stocked out. Should be reported."""
        other_product = Product(domain=self.TEST_DOMAIN, name='Test Product2', code_='tp2', unit='each')
        other_product.save()

        assign_products_to_location(self.facility, [self.product, other_product])

        create_stock_report(self.facility, {'tp': 0})
        create_stock_report(self.facility, {'tp2': 10})

        generated = list(OnGoingStockouts(self.TEST_DOMAIN).get_notifications())
        self.assertEqual(len(generated), 1)
        self.assertEqual(generated[0].user.get_id, self.user.get_id)

    def test_multiple_users(self):
        """Each user will get their own notification."""
        assign_products_to_location(self.facility, [self.product])
        create_stock_report(self.facility, {'tp': 0})
        other_user = bootstrap_web_user(
            username='test2', domain=self.TEST_DOMAIN, phone_number='+44445', location=self.district,
            password='dummy', email='test@example.com', user_data={}
        )

        generated = list(OnGoingStockouts(self.TEST_DOMAIN).get_notifications())
        self.assertEqual(len(generated), 2)
        self.assertEqual({generated[0].user.get_id, generated[1].user.get_id},
                         {self.user.get_id, other_user.get_id})

    def test_product_type_filter(self):
        """User can recieve notifications for only certain product type."""
        bootstrap_web_user(
            username='test2', domain=self.TEST_DOMAIN, phone_number='+44445', location=self.district,
            password='dummy', email='test@example.com', user_data={}, program_id=self.program.get_id
        )
        create_stock_report(self.facility, {'tp': 0})
        generated = list(OnGoingStockouts(self.TEST_DOMAIN).get_notifications())
        self.assertEqual(len(generated), 1)


class UrgentStockoutNotificationTestCase(EWSTestCase):

    TEST_DOMAIN = 'notifications-test-ews3'

    @classmethod
    def setUpClass(cls):
        cls.backend, cls.sms_backend_mapping = setup_default_sms_test_backend()
        cls.domain = prepare_domain(cls.TEST_DOMAIN)
        cls.program = Program(domain=cls.TEST_DOMAIN, name='Test Program')
        cls.program.save()

    def setUp(self):
        self.product = Product(domain=self.TEST_DOMAIN, name='Test Product', code_='tp', unit='each',
                               program_id=self.program.get_id)
        self.product.save()

        self.country = make_loc('test-country', 'Test country', self.TEST_DOMAIN, 'country')
        self.region = make_loc('test-region', 'Test Region', self.TEST_DOMAIN, 'region', parent=self.country)
        self.district = make_loc('test-district', 'Test District', self.TEST_DOMAIN, 'district',
                                 parent=self.region)

        self.facility = make_loc('test-facility', 'Test Facility', self.TEST_DOMAIN, 'Polyclinic', self.district)
        self.other_facility = make_loc('test-facility2', 'Test Facility 2', self.TEST_DOMAIN, 'Polyclinic',
                                       self.district)
        self.last_facility = make_loc('test-facility3', 'Test Facility 3', self.TEST_DOMAIN, 'Polyclinic',
                                      self.district)
        self.user = bootstrap_web_user(
            username='test', domain=self.TEST_DOMAIN, phone_number='+4444', location=self.region,
            email='test@example.com', password='dummy', user_data={}
        )

    def tearDown(self):
        for location in Location.by_domain(self.TEST_DOMAIN):
            location.delete()

        for user in WebUser.by_domain(self.TEST_DOMAIN):
            user.delete()

        for vn in VerifiedNumber.by_domain(self.TEST_DOMAIN):
            vn.delete()

        for product in Product.by_domain(self.TEST_DOMAIN):
            product.delete()

    def test_all_facility_stockout(self):
        """Send a notification because all facilities are stocked out of a product."""
        assign_products_to_location(self.facility, [self.product])
        assign_products_to_location(self.other_facility, [self.product])
        assign_products_to_location(self.last_facility, [self.product])

        create_stock_report(self.facility, {'tp': 0})
        create_stock_report(self.other_facility, {'tp': 0})
        create_stock_report(self.last_facility, {'tp': 0})

        generated = list(UrgentStockoutAlert(self.TEST_DOMAIN).get_notifications())
        self.assertEqual(len(generated), 1)
        self.assertEqual(generated[0].user.get_id, self.user.get_id)

    def test_majority_facility_stockout(self):
        """Send a notification because > 50% of the facilities are stocked out of a product."""
        assign_products_to_location(self.facility, [self.product])
        assign_products_to_location(self.other_facility, [self.product])
        assign_products_to_location(self.last_facility, [self.product])

        create_stock_report(self.facility, {'tp': 0})
        create_stock_report(self.other_facility, {'tp': 0})
        create_stock_report(self.last_facility, {'tp': 10})

        generated = list(UrgentStockoutAlert(self.TEST_DOMAIN).get_notifications())
        self.assertEqual(len(generated), 1)
        self.assertEqual(generated[0].user.get_id, self.user.get_id)

    def test_minority_facility_stockout(self):
        """No notification because < 50% of the facilities are stocked out of a product."""
        assign_products_to_location(self.facility, [self.product])
        assign_products_to_location(self.other_facility, [self.product])
        assign_products_to_location(self.last_facility, [self.product])

        create_stock_report(self.facility, {'tp': 0})
        create_stock_report(self.other_facility, {'tp': 10})
        create_stock_report(self.last_facility, {'tp': 10})

        generated = list(UrgentStockoutAlert(self.TEST_DOMAIN).get_notifications())
        self.assertEqual(len(generated), 0)

    def test_partial_stock_coverage(self):
        """
        Handle the case when not all facilities are expected to have stocked a
        given product. i.e. if only one facility is expected to have a certain
        product and it is stocked out then that is an urgent stockout.
        """
        assign_products_to_location(self.facility, [self.product])

        create_stock_report(self.facility, {'tp': 0})

        generated = list(UrgentStockoutAlert(self.TEST_DOMAIN).get_notifications())
        self.assertEqual(len(generated), 1)
        self.assertEqual(generated[0].user.get_id, self.user.get_id)

    def test_multiple_users(self):
        """Each user will get their own urgent stockout notification."""
        other_user = bootstrap_web_user(
            username='test2', domain=self.TEST_DOMAIN, phone_number='+44445', location=self.region,
            password='dummy', email='test@example.com', user_data={}
        )
        assign_products_to_location(self.facility, [self.product])
        assign_products_to_location(self.other_facility, [self.product])
        assign_products_to_location(self.last_facility, [self.product])

        create_stock_report(self.facility, {'tp': 0})
        create_stock_report(self.other_facility, {'tp': 0})
        create_stock_report(self.last_facility, {'tp': 0})
        generated = list(UrgentStockoutAlert(self.TEST_DOMAIN).get_notifications())
        self.assertEqual(len(generated), 2)
        self.assertEqual({generated[0].user.get_id, generated[1].user.get_id},
                         {self.user.get_id, other_user.get_id})

    def test_country_user(self):
        """Country as well as region users should get notifications."""
        other_user = bootstrap_web_user(
            username='test2', domain=self.TEST_DOMAIN, phone_number='+44445', location=self.country,
            password='dummy', email='test@example.com', user_data={}
        )
        assign_products_to_location(self.facility, [self.product])
        assign_products_to_location(self.other_facility, [self.product])
        assign_products_to_location(self.last_facility, [self.product])

        create_stock_report(self.facility, {'tp': 0})
        create_stock_report(self.other_facility, {'tp': 0})
        create_stock_report(self.last_facility, {'tp': 0})
        generated = list(UrgentStockoutAlert(self.TEST_DOMAIN).get_notifications())
        self.assertEqual(len(generated), 2)
        self.assertEqual({generated[0].user.get_id, generated[1].user.get_id},
                         {self.user.get_id, other_user.get_id})

    def test_product_type_filter(self):
        """
        Notifications will not be sent if the stockout is a product type does
        not interest the user.
        """

        self.user.get_domain_membership(self.TEST_DOMAIN).program_id = self.program.get_id
        self.user.save()

        program = Program(domain=self.TEST_DOMAIN, name='Test Program 2')
        program.save()

        bootstrap_web_user(
            username='test2', domain=self.TEST_DOMAIN, phone_number='+44445', location=self.district,
            password='dummy', email='test@example.com', user_data={}, program_id=program.get_id
        )

        assign_products_to_location(self.facility, [self.product])
        assign_products_to_location(self.other_facility, [self.product])
        assign_products_to_location(self.last_facility, [self.product])

        create_stock_report(self.facility, {'tp': 0})
        create_stock_report(self.other_facility, {'tp': 0})
        create_stock_report(self.last_facility, {'tp': 0})

        generated = list(UrgentStockoutAlert(self.TEST_DOMAIN).get_notifications())
        self.assertEqual(len(generated), 1)
        self.assertEqual(generated[0].user.get_id, self.user.get_id)


class UrgentNonReportingNotificationTestCase(EWSTestCase):
    """Trigger notifications for regions with urgent stockouts."""
    TEST_DOMAIN = 'notifications-test-ews4'

    @classmethod
    def setUpClass(cls):
        cls.backend, cls.sms_backend_mapping = setup_default_sms_test_backend()
        cls.domain = prepare_domain(cls.TEST_DOMAIN)
        cls.program = Program(domain=cls.TEST_DOMAIN, name='Test Program')
        cls.program.save()

    def setUp(self):
        self.product = Product(domain=self.TEST_DOMAIN, name='Test Product', code_='tp', unit='each',
                               program_id=self.program.get_id)
        self.product.save()

        self.country = make_loc('test-country', 'Test country', self.TEST_DOMAIN, 'country')
        self.region = make_loc('test-region', 'Test Region', self.TEST_DOMAIN, 'region', parent=self.country)
        self.district = make_loc('test-district', 'Test District', self.TEST_DOMAIN, 'district',
                                 parent=self.region)

        self.facility = make_loc('test-facility', 'Test Facility', self.TEST_DOMAIN, 'Polyclinic', self.district)
        self.other_facility = make_loc('test-facility2', 'Test Facility 2', self.TEST_DOMAIN, 'Polyclinic',
                                       self.district)
        self.last_facility = make_loc('test-facility3', 'Test Facility 3', self.TEST_DOMAIN, 'Polyclinic',
                                      self.district)
        self.user = bootstrap_web_user(
            username='test', domain=self.TEST_DOMAIN, phone_number='+4444', location=self.region,
            email='test@example.com', password='dummy', user_data={}
        )

    def tearDown(self):
        for location in Location.by_domain(self.TEST_DOMAIN):
            location.delete()

        for user in WebUser.by_domain(self.TEST_DOMAIN):
            user.delete()

        for vn in VerifiedNumber.by_domain(self.TEST_DOMAIN):
            vn.delete()

        for product in Product.by_domain(self.TEST_DOMAIN):
            product.delete()

    def test_all_facility_not_report(self):
        """Send a notification because all facilities don't send report."""
        assign_products_to_location(self.facility, [self.product])
        assign_products_to_location(self.other_facility, [self.product])
        assign_products_to_location(self.last_facility, [self.product])

        generated = list(UrgentNonReporting(self.TEST_DOMAIN).get_notifications())
        self.assertEqual(len(generated), 1)
        self.assertEqual(generated[0].user.get_id, self.user.get_id)

    def test_majority_facility_not_report(self):
        """Send a notification because > 50% of the facilities don't send report."""
        assign_products_to_location(self.facility, [self.product])
        assign_products_to_location(self.other_facility, [self.product])
        assign_products_to_location(self.last_facility, [self.product])

        create_stock_report(self.last_facility, {'tp': 10})

        generated = list(UrgentNonReporting(self.TEST_DOMAIN).get_notifications())
        self.assertEqual(len(generated), 1)
        self.assertEqual(generated[0].user.get_id, self.user.get_id)

    def test_minority_facility_stockout(self):
        """No notification because < 50% of the facilities don't send report."""
        assign_products_to_location(self.facility, [self.product])
        assign_products_to_location(self.other_facility, [self.product])
        assign_products_to_location(self.last_facility, [self.product])

        create_stock_report(self.other_facility, {'tp': 10})
        create_stock_report(self.last_facility, {'tp': 10})

        generated = list(UrgentStockoutAlert(self.TEST_DOMAIN).get_notifications())
        self.assertEqual(len(generated), 0)

    def test_multiple_users(self):
        """Each user will get their own urgent stockout notification."""
        other_user = bootstrap_web_user(
            username='test2', domain=self.TEST_DOMAIN, phone_number='+44445', location=self.region,
            password='dummy', email='test@example.com', user_data={}
        )
        assign_products_to_location(self.facility, [self.product])
        assign_products_to_location(self.other_facility, [self.product])
        assign_products_to_location(self.last_facility, [self.product])

        generated = list(UrgentNonReporting(self.TEST_DOMAIN).get_notifications())
        self.assertEqual(len(generated), 2)
        self.assertEqual({generated[0].user.get_id, generated[1].user.get_id},
                         {self.user.get_id, other_user.get_id})

    def test_country_user(self):
        """Country as well as region users should get notifications."""
        other_user = bootstrap_web_user(
            username='test2', domain=self.TEST_DOMAIN, phone_number='+44445', location=self.country,
            password='dummy', email='test@example.com', user_data={}
        )
        assign_products_to_location(self.facility, [self.product])
        assign_products_to_location(self.other_facility, [self.product])
        assign_products_to_location(self.last_facility, [self.product])

        generated = list(UrgentNonReporting(self.TEST_DOMAIN).get_notifications())
        self.assertEqual(len(generated), 2)
        self.assertEqual(
            {generated[0].user.get_id, generated[1].user.get_id},
            {self.user.get_id, other_user.get_id}
        )

    def test_product_type_filter(self):
        """
        Notifications will not be sent if the stockout is a product type does
        not interest the user.
        """

        self.user.get_domain_membership(self.TEST_DOMAIN).program_id = self.program.get_id
        self.user.save()

        program = Program(domain=self.TEST_DOMAIN, name='Test Program 2')
        program.save()

        other_user = bootstrap_web_user(
            username='test2', domain=self.TEST_DOMAIN, phone_number='+44445', location=self.region,
            password='dummy', email='test@example.com', user_data={}
        )

        assign_products_to_location(self.facility, [self.product])
        assign_products_to_location(self.other_facility, [self.product])
        assign_products_to_location(self.last_facility, [self.product])

        generated = list(UrgentNonReporting(self.TEST_DOMAIN).get_notifications())
        self.assertEqual(len(generated), 2)
        self.assertEqual({generated[0].user.get_id, generated[1].user.get_id},
                         {self.user.get_id, other_user.get_id})


class SMSNotificationTestCase(EWSTestCase):
    """Saved notifications should trigger SMS to users with associated contacts."""
    TEST_DOMAIN = 'notifications-test-ews5'

    @classmethod
    def setUpClass(cls):
        cls.backend, cls.sms_backend_mapping = setup_default_sms_test_backend()
        cls.domain = prepare_domain(cls.TEST_DOMAIN)

    def setUp(self):
        self.district = make_loc('test-district', 'Test District', self.TEST_DOMAIN, 'district')
        self.user = bootstrap_web_user(
            username='test', domain=self.TEST_DOMAIN, phone_number='+4444', location=self.district,
            email='test@example.com', password='dummy'
        )
        set_sms_notifications(self.domain, self.user, True)
        self.notification = Notification(self.TEST_DOMAIN, self.user, 'test')

    def tearDown(self):
        for location in Location.by_domain(self.TEST_DOMAIN):
            location.delete()

        for user in WebUser.by_domain(self.TEST_DOMAIN):
            user.delete()

        for vn in VerifiedNumber.by_domain(self.TEST_DOMAIN):
            vn.delete()

    def test_send_sms(self):
        """Successful SMS sent."""
        with mock.patch('custom.ewsghana.alerts.alert.send_sms') as send:
            self.notification.send()
            self.assertTrue(send.called)
            args, kwargs = send.call_args
            domain, user, phone_number, text = args

            self.assertEqual(self.notification.message, text)
            self.assertEqual(phone_number, '+4444')

    def test_no_connections(self):
        """No message will be sent if contact doesn't have an associated connection."""
        self.user.phone_numbers = []
        self.user.save()
        with mock.patch('custom.ewsghana.alerts.alert.send_sms') as send:
            self.notification.send()
            self.assertFalse(send.called)

    def test_opt_out(self):
        """No message will be sent if the user has opted out of the notifications."""
        set_sms_notifications(self.domain, self.user, False)
        with mock.patch('custom.ewsghana.alerts.alert.send_sms') as send:
            self.notification.send()
            self.assertFalse(send.called)
