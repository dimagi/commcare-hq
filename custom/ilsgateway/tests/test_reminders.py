from datetime import datetime

from django.test.testcases import TestCase

from corehq.apps.accounting import generator
from corehq.apps.commtrack.tests.util import make_loc
from corehq.apps.domain.models import Domain
from corehq.apps.sms.models import SMS
from corehq.apps.sms.tests.util import setup_default_sms_test_backend

from custom.ilsgateway.models import SupplyPointStatus, SupplyPointStatusTypes
from custom.ilsgateway.tanzania.reminders import REMINDER_R_AND_R_FACILITY, REMINDER_R_AND_R_DISTRICT, \
    DELIVERY_REMINDER_FACILITY, DELIVERY_REMINDER_DISTRICT, REMINDER_STOCKONHAND, SUPERVISION_REMINDER
from custom.ilsgateway.tanzania.reminders.delivery import DeliveryReminder
from custom.ilsgateway.tanzania.reminders.randr import RandrReminder
from custom.ilsgateway.tanzania.reminders.stockonhand import SOHReminder
from custom.ilsgateway.tanzania.reminders.supervision import SupervisionReminder
from custom.ilsgateway.tests.handlers.utils import prepare_domain
from custom.logistics.tests.utils import bootstrap_user

TEST_DOMAIN = 'randr-reminder'


class TestReminders(TestCase):

    @classmethod
    def setUpClass(cls):
        cls.sms_backend, cls.sms_backend_mapping = setup_default_sms_test_backend()
        domain = prepare_domain(TEST_DOMAIN)
        mohsw = make_loc(code="moh1", name="Test MOHSW 1", type="MOHSW", domain=domain.name)

        msdzone = make_loc(code="msd1", name="MSD Zone 1", type="MSDZONE",
                           domain=domain.name, parent=mohsw)

        region = make_loc(code="reg1", name="Test Region 1", type="REGION",
                          domain=domain.name, parent=msdzone)
        cls.district = make_loc(code="dis1", name="Test District 1", type="DISTRICT",
                                domain=domain.name, parent=region)
        cls.facility = make_loc(code="loc1", name="Test Facility 1", type="FACILITY",
                                domain=domain.name, parent=cls.district)
        cls.facility.metadata['group'] = 'B'
        cls.facility2 = make_loc(code="loc2", name="Test Facility 2", type="FACILITY",
                                 domain=domain.name, parent=cls.district)
        cls.facility2.metadata['group'] = 'C'
        cls.facility.save()
        cls.facility2.save()

        cls.user1 = bootstrap_user(
            cls.facility, username='test', domain=domain.name, home_loc='loc1', phone_number='5551234',
            first_name='test', last_name='Test'
        )
        bootstrap_user(cls.facility2, username='test1', domain=domain.name, home_loc='loc2',
                       phone_number='5555678', first_name='test1', last_name='Test')
        bootstrap_user(cls.district, username='test2', domain=domain.name, home_loc='dis1', phone_number='555',
                       first_name='test1', last_name='Test')
        bootstrap_user(cls.district, username='msd_person', domain=domain.name, phone_number='111',
                       first_name='MSD', last_name='Person', user_data={'role': 'MSD'})

    @classmethod
    def tearDownClass(cls):
        cls.sms_backend_mapping.delete()
        cls.sms_backend.delete()
        Domain.get_by_name(TEST_DOMAIN).delete()
        generator.delete_all_subscriptions()

    def tearDown(self):
        SMS.objects.all().delete()
        SupplyPointStatus.objects.all().delete()

    def test_randr_reminder_facility(self):
        date = datetime(2015, 5, 1)
        RandrReminder(TEST_DOMAIN, date).send()
        self.assertEqual(SMS.objects.count(), 1)

        statuses = SupplyPointStatus.objects.filter(status_type=SupplyPointStatusTypes.R_AND_R_FACILITY)
        self.assertEqual(statuses.count(), 1)

        smses = SMS.objects.all()
        self.assertEqual(smses.first().text, unicode(REMINDER_R_AND_R_FACILITY))
        self.assertEqual(
            statuses.values_list('location_id', flat=True)[0], self.facility.get_id
        )

        now = datetime.utcnow()

        RandrReminder(TEST_DOMAIN, date).send()
        self.assertEqual(SMS.objects.filter(date__gte=now).count(), 0)

    def test_randr_reminder_district(self):
        date = datetime(2015, 5, 1)
        RandrReminder(TEST_DOMAIN, date, 'DISTRICT').send()
        self.assertEqual(SMS.objects.count(), 1)

        statuses = SupplyPointStatus.objects.filter(status_type=SupplyPointStatusTypes.R_AND_R_DISTRICT)
        self.assertEqual(statuses.count(), 1)

        smses = SMS.objects.all()
        self.assertEqual(smses.first().text, unicode(REMINDER_R_AND_R_DISTRICT))
        self.assertEqual(
            statuses.values_list('location_id', flat=True)[0], self.district.get_id
        )

        now = datetime.utcnow()

        RandrReminder(TEST_DOMAIN, date, 'DISTRICT').send()
        self.assertEqual(SMS.objects.filter(date__gte=now).count(), 0)

    def test_delivery_reminder_facility(self):
        date = datetime(2015, 5, 1)
        DeliveryReminder(TEST_DOMAIN, date).send()
        self.assertEqual(SMS.objects.count(), 1)

        statuses = SupplyPointStatus.objects.filter(status_type=SupplyPointStatusTypes.DELIVERY_FACILITY)
        self.assertEqual(statuses.count(), 1)

        smses = SMS.objects.all()
        self.assertEqual(smses.first().text, unicode(DELIVERY_REMINDER_FACILITY))
        self.assertEqual(
            statuses.values_list('location_id', flat=True)[0], self.facility2.get_id
        )

        now = datetime.utcnow()

        DeliveryReminder(TEST_DOMAIN, date).send()
        self.assertEqual(SMS.objects.filter(date__gte=now).count(), 0)

    def test_delivery_reminder_district(self):
        date = datetime(2015, 5, 1)
        DeliveryReminder(TEST_DOMAIN, date, 'DISTRICT').send()
        self.assertEqual(SMS.objects.count(), 1)

        statuses = SupplyPointStatus.objects.filter(status_type=SupplyPointStatusTypes.DELIVERY_DISTRICT)
        self.assertEqual(statuses.count(), 1)

        smses = SMS.objects.all()
        self.assertEqual(smses.first().text, unicode(DELIVERY_REMINDER_DISTRICT))
        self.assertEqual(
            statuses.values_list('location_id', flat=True)[0], self.district.get_id
        )

        now = datetime.utcnow()

        DeliveryReminder(TEST_DOMAIN, date, 'DISTRICT').send()
        self.assertEqual(SMS.objects.filter(date__gte=now).count(), 0)

    def test_soh_reminder(self):
        date = datetime(2015, 5, 1)
        SOHReminder(TEST_DOMAIN, date).send()

        self.assertEqual(SMS.objects.count(), 2)

        smses = SMS.objects.all()
        self.assertEqual(smses.first().text, unicode(REMINDER_STOCKONHAND))

        statuses = SupplyPointStatus.objects.filter(status_type=SupplyPointStatusTypes.SOH_FACILITY)
        self.assertEqual(statuses.count(), 2)
        self.assertSetEqual(
            set(statuses.values_list('location_id', flat=True)), {self.facility.get_id, self.facility2.get_id}
        )

    def test_supervision_reminder(self):
        date = datetime(2015, 5, 1)
        SupervisionReminder(TEST_DOMAIN, date).send()
        self.assertEqual(SMS.objects.count(), 2)

        statuses = SupplyPointStatus.objects.filter(status_type=SupplyPointStatusTypes.SUPERVISION_FACILITY)
        self.assertEqual(statuses.count(), 2)

        smses = SMS.objects.all()
        self.assertEqual(smses.first().text, unicode(SUPERVISION_REMINDER))
        self.assertSetEqual(
            set(statuses.values_list('location_id', flat=True)), {self.facility.get_id, self.facility2.get_id}
        )

        now = datetime.utcnow()

        SupervisionReminder(TEST_DOMAIN, date).send()
        self.assertEqual(SMS.objects.filter(date__gte=now).count(), 0)
