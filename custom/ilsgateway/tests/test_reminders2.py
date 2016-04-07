from datetime import datetime

from corehq.apps.commtrack.models import CommtrackConfig, ConsumptionConfig
from corehq.apps.consumption.shortcuts import set_default_consumption_for_supply_point
from corehq.apps.sms.tests import setup_default_sms_test_backend, delete_domain_phone_numbers
from corehq.util.translation import localize
from custom.ilsgateway.models import SupplyPointStatus, DeliveryGroups, SupplyPointStatusTypes, \
    SupplyPointStatusValues, SLABConfig
from custom.ilsgateway.slab.messages import REMINDER_STOCKOUT
from custom.ilsgateway.slab.reminders.stockout import StockoutReminder
from custom.ilsgateway.tanzania.reminders import update_statuses
from custom.ilsgateway.tanzania.reminders.delivery import DeliveryReminder
from custom.ilsgateway.tanzania.reminders.randr import RandrReminder
from custom.ilsgateway.tanzania.reminders.soh_thank_you import SOHThankYouReminder
from custom.ilsgateway.tanzania.reminders.stockonhand import SOHReminder
from custom.ilsgateway.tanzania.reminders.supervision import SupervisionReminder
from custom.ilsgateway.tests.handlers.utils import ILSTestScript, TEST_DOMAIN, prepare_domain, create_products
from custom.ilsgateway.utils import make_loc
from custom.logistics.tests.utils import bootstrap_user


class RemindersTest(ILSTestScript):
    @classmethod
    def setUpClass(cls):
        cls.sms_backend, cls.sms_backend_mapping = setup_default_sms_test_backend()
        cls.domain = prepare_domain(TEST_DOMAIN)

        cls.district = make_loc(code="dis1", name="Test District 1", type="DISTRICT",
                                domain=TEST_DOMAIN)
        cls.facility = make_loc(code="loc1", name="Test Facility 1", type="FACILITY",
                                domain=TEST_DOMAIN, parent=cls.district)
        cls.facility_sp_id = cls.facility.sql_location.supply_point_id
        cls.user1 = bootstrap_user(
            cls.facility, username='test_user', domain=TEST_DOMAIN, home_loc='loc1', phone_number='5551234',
            first_name='test', last_name='Test'
        )
        create_products(cls, TEST_DOMAIN, ["id", "dp", "fs", "md", "ff", "dx", "bp", "pc", "qi", "jd", "mc", "ip"])

    def tearDown(self):
        SupplyPointStatus.objects.all().delete()

    @classmethod
    def tearDownClass(cls):
        delete_domain_phone_numbers(TEST_DOMAIN)
        cls.sms_backend_mapping.delete()
        cls.sms_backend.delete()
        cls.domain.delete()


class TestStockOnHandReminders(RemindersTest):

    def test_basic_list(self):
        people = list(SOHReminder(TEST_DOMAIN, datetime.utcnow()).get_people())
        self.assertEqual(len(people), 1)
        self.assertEqual(people[0].get_id, self.user1.get_id)

    def test_district_exclusion(self):
        self.user1.location_id = self.district.get_id
        self.user1.save()
        people = list(SOHReminder(TEST_DOMAIN, datetime.utcnow()).get_people())
        self.assertEqual(len(people), 0)
        self.user1.location_id = self.facility.get_id
        self.user1.save()

    def test_report_exclusion(self):
        now = datetime.utcnow()
        people = list(SOHReminder(TEST_DOMAIN, datetime.utcnow()).get_people())
        self.assertEqual(len(people), 1)
        script = """
            5551234 > Hmk Id 400 Dp 569 Ip 678
        """
        self.run_script(script)

        people = list(SOHReminder(TEST_DOMAIN, now).get_people())
        self.assertEqual(len(people), 0)

        people = list(SOHReminder(TEST_DOMAIN, datetime.utcnow()).get_people())
        self.assertEqual(len(people), 1)


class TestDeliveryReminder(RemindersTest):

    def setUp(self):
        self.facility.metadata['group'] = DeliveryGroups().current_delivering_group()
        self.facility.save()

    def test_group_exclusion(self):
        people = list(DeliveryReminder(TEST_DOMAIN, datetime.utcnow()).get_people())
        self.assertEqual(len(people), 1)
        self.assertEqual(people[0].get_id, self.user1.get_id)

        self.facility.metadata['group'] = DeliveryGroups().current_submitting_group()
        self.facility.save()
        people = list(DeliveryReminder(TEST_DOMAIN, datetime.utcnow()).get_people())
        self.assertEqual(len(people), 0)

        self.facility.metadata['group'] = DeliveryGroups().current_processing_group()
        self.facility.save()
        people = list(DeliveryReminder(TEST_DOMAIN, datetime.utcnow()).get_people())
        self.assertEqual(len(people), 0)

    def test_report_exclusion(self):
        now = datetime.utcnow()
        people = list(DeliveryReminder(TEST_DOMAIN, now).get_people())
        self.assertEqual(len(people), 1)

        # reports for a different type shouldn't update status
        script = """
            5551234 > nimetuma
        """
        self.run_script(script)
        people = list(DeliveryReminder(TEST_DOMAIN, now).get_people())
        self.assertEqual(len(people), 1)

        script = """
            5551234 > nimepokea
        """
        self.run_script(script)
        people = list(DeliveryReminder(TEST_DOMAIN, now).get_people())
        self.assertEqual(len(people), 0)

        people = list(DeliveryReminder(TEST_DOMAIN, datetime.utcnow()).get_people())
        self.assertEqual(len(people), 1)


class TestRandRReminder(RemindersTest):

    def setUp(self):
        self.facility.metadata['group'] = DeliveryGroups().current_submitting_group()
        self.facility.save()

    def test_group_exclusion(self):
        people = list(RandrReminder(TEST_DOMAIN, datetime.utcnow()).get_people())
        self.assertEqual(len(people), 1)
        self.assertEqual(people[0].get_id, self.user1.get_id)

        self.facility.metadata['group'] = DeliveryGroups().current_delivering_group()
        self.facility.save()
        people = list(RandrReminder(TEST_DOMAIN, datetime.utcnow()).get_people())
        self.assertEqual(len(people), 0)

        self.facility.metadata['group'] = DeliveryGroups().current_processing_group()
        self.facility.save()
        people = list(RandrReminder(TEST_DOMAIN, datetime.utcnow()).get_people())
        self.assertEqual(len(people), 0)

    def test_report_exclusion(self):
        now = datetime.utcnow()
        people = list(RandrReminder(TEST_DOMAIN, now).get_people())
        self.assertEqual(len(people), 1)

        # reports for a different type shouldn't update status
        script = """
            5551234 > nimepokea
        """
        self.run_script(script)
        people = list(RandrReminder(TEST_DOMAIN, now).get_people())
        self.assertEqual(len(people), 1)

        script = """
            5551234 > nimetuma
        """
        self.run_script(script)
        people = list(RandrReminder(TEST_DOMAIN, now).get_people())
        self.assertEqual(len(people), 0)

        people = list(RandrReminder(TEST_DOMAIN, datetime.utcnow()).get_people())
        self.assertEqual(len(people), 1)


class TestSupervisionStatusSet(RemindersTest):

    def setUp(self):
        self.facility.metadata['group'] = DeliveryGroups().current_submitting_group()
        self.facility.save()

    def test_reminder_set(self):
        now = datetime.utcnow()
        people = list(RandrReminder(TEST_DOMAIN, datetime.utcnow()).get_people())
        self.assertEqual(len(people), 1)
        self.assertEqual(people[0].get_id, self.user1.get_id)

        self.facility.metadata['group'] = DeliveryGroups().current_delivering_group()
        self.facility.save()
        people = list(SupervisionReminder(TEST_DOMAIN, datetime.utcnow()).get_people())
        self.assertEqual(len(people), 1)

        update_statuses(
            [self.facility.get_id],
            SupplyPointStatusTypes.SUPERVISION_FACILITY,
            SupplyPointStatusValues.REMINDER_SENT
        )

        people = list(SupervisionReminder(TEST_DOMAIN, now).get_people())
        self.assertEqual(len(people), 0)

        SupplyPointStatus.objects.all().delete()

        people = list(SupervisionReminder(TEST_DOMAIN, now).get_people())
        self.assertEqual(len(people), 1)

        SupplyPointStatus.objects.create(
            status_type=SupplyPointStatusTypes.SUPERVISION_FACILITY,
            status_value=SupplyPointStatusValues.RECEIVED,
            location_id=self.facility.get_id
        )
        people = list(SupervisionReminder(TEST_DOMAIN, now).get_people())
        self.assertEqual(len(people), 0)


class TestSOHThankYou(RemindersTest):

    def test_group_exclusion(self):
        now = datetime.utcnow()
        people = list(SOHThankYouReminder(TEST_DOMAIN, now).get_people())
        self.assertEqual(len(people), 0)

        script = """
            5551234 > soh id 100
        """
        self.run_script(script)

        people = list(SOHThankYouReminder(TEST_DOMAIN, now).get_people())
        self.assertEqual(len(people), 1)
        self.assertEqual(len(list(SOHThankYouReminder(TEST_DOMAIN, datetime.utcnow()).get_people())), 0)


class TestStockOut(RemindersTest):

    @classmethod
    def setUpClass(cls):
        super(TestStockOut, cls).setUpClass()
        cls.facility2 = make_loc(code="loc2", name="Test Facility 2", type="FACILITY",
                                 domain=TEST_DOMAIN, parent=cls.district)
        cls.user2 = bootstrap_user(
            cls.facility2, username='test_user2', domain=TEST_DOMAIN, home_loc='loc2', phone_number='5551235',
            first_name='test', last_name='Test'
        )
        SLABConfig.objects.create(
            is_pilot=True,
            sql_location=cls.facility.sql_location
        )

        slab_config = SLABConfig.objects.create(
            is_pilot=True,
            sql_location=cls.facility2.sql_location
        )
        slab_config.closest_supply_points.add(cls.facility.sql_location)
        slab_config.save()

        config = CommtrackConfig.for_domain(TEST_DOMAIN)
        config.use_auto_consumption = False
        config.individual_consumption_defaults = True
        config.consumption_config = ConsumptionConfig(
            use_supply_point_type_default_consumption=True,
            exclude_invalid_periods=True
        )
        config.save()

        set_default_consumption_for_supply_point(TEST_DOMAIN, cls.id.get_id, cls.facility_sp_id, 100)
        set_default_consumption_for_supply_point(TEST_DOMAIN, cls.dp.get_id, cls.facility_sp_id, 100)
        set_default_consumption_for_supply_point(TEST_DOMAIN, cls.ip.get_id, cls.facility_sp_id, 100)

    def test_reminder(self):
        now = datetime.utcnow()
        self.assertEqual(0, len(list(StockoutReminder(TEST_DOMAIN, now).get_people())))
        script = """
            5551234 > Hmk Id 400 Dp 620 Ip 678
        """
        self.run_script(script)
        self.assertEqual(1, len(list(StockoutReminder(TEST_DOMAIN, now).get_people())))

        script = """
            5551235 > Hmk Id 0 Dp 0 Ip 0
        """
        self.run_script(script)

        with localize('sw'):
            reminder_stockout = unicode(REMINDER_STOCKOUT)

        StockoutReminder(TEST_DOMAIN, now).send()
        script = """
            5551235 < %s
        """ % reminder_stockout % {
            'products_list': 'dp, id, ip',
            'overstocked_list': 'Test Facility 1 (dp, ip)'
        }
        self.run_script(script)
