from __future__ import absolute_import
from __future__ import unicode_literals
from datetime import datetime, timedelta

import mock
from django.test import TestCase
from django.utils import translation

from corehq.apps.sms.tests.util import setup_default_sms_test_backend, delete_domain_phone_numbers
from custom.ilsgateway.models import DeliveryGroups, SupplyPointStatus
from custom.ilsgateway.tanzania.reminders import TEST_HANDLER_CONFIRM, \
    REMINDER_MONTHLY_DELIVERY_SUMMARY, REMINDER_MONTHLY_SOH_SUMMARY
from custom.ilsgateway.tanzania.reminders.reports import get_district_people, \
    construct_delivery_summary, construct_soh_summary
from custom.ilsgateway.tests.handlers.utils import prepare_domain
from custom.ilsgateway.tests.handlers.utils import TEST_DOMAIN, create_products
from custom.ilsgateway.tests.test_script import TestScript
from custom.ilsgateway.tests.utils import bootstrap_user
from custom.ilsgateway.utils import make_loc
import six


class TestReportGroups(TestCase):

    @classmethod
    def setUpClass(cls):
        super(TestReportGroups, cls).setUpClass()
        cls.sms_backend, cls.sms_backend_mapping = setup_default_sms_test_backend()
        cls.domain = prepare_domain(TEST_DOMAIN)

        cls.district = make_loc(code="dis1", name="Test District 1", type="DISTRICT",
                                domain=TEST_DOMAIN)
        cls.facility = make_loc(code="loc1", name="Test Facility 1", type="FACILITY",
                                domain=TEST_DOMAIN, parent=cls.district)
        cls.user1 = bootstrap_user(
            cls.district, username='test_user', domain=TEST_DOMAIN, home_loc='dis1', phone_number='5551234',
            first_name='test', last_name='Test'
        )

    @classmethod
    def tearDownClass(cls):
        delete_domain_phone_numbers(TEST_DOMAIN)
        cls.sms_backend.delete()
        cls.sms_backend_mapping.delete()
        cls.user1.delete()
        cls.domain.delete()
        super(TestReportGroups, cls).tearDownClass()

    def test_basic_list(self):
        people = list(get_district_people(TEST_DOMAIN))
        self.assertEqual(len(people), 1)
        self.assertEqual(people[0].get_id, self.user1.get_id)

    def test_district_exclusion(self):
        self.user1.location_id = self.facility.get_id
        self.user1.save()
        people = list(get_district_people(TEST_DOMAIN))
        self.assertEqual(len(people), 0)

        self.user1.location_id = self.district.get_id
        self.user1.save()
        people = list(get_district_people(TEST_DOMAIN))
        self.assertEqual(len(people), 1)


class TestReportSummaryBase(TestScript):
    """
    Stub base class for the report tests. Provides some convenience methods
    and does some initial setup of facility and district users and supply
    points.
    """

    @classmethod
    def relevant_group(cls):
        raise NotImplemented()

    @classmethod
    def setUpClass(cls):
        super(TestReportSummaryBase, cls).setUpClass()
        delete_domain_phone_numbers(TEST_DOMAIN)
        cls.sms_backend, cls.sms_backend_mapping = setup_default_sms_test_backend()
        cls.domain = prepare_domain(TEST_DOMAIN)

        cls.district = make_loc(code="dis1", name="TEST DISTRICT", type="DISTRICT", domain=TEST_DOMAIN,
                                metadata={'group': DeliveryGroups().current_submitting_group()})
        cls.facility = make_loc(code="d10001", name="Test Facility 1", type="FACILITY",
                                domain=TEST_DOMAIN, parent=cls.district,
                                metadata={'group': DeliveryGroups().current_submitting_group()})
        cls.facility2 = make_loc(code="d10002", name="Test Facility 2", type="FACILITY",
                                 domain=TEST_DOMAIN, parent=cls.district,
                                 metadata={'group': DeliveryGroups().current_delivering_group()})
        cls.facility3 = make_loc(code="d10003", name="Test Facility 3", type="FACILITY",
                                 domain=TEST_DOMAIN, parent=cls.district,
                                 metadata={'group': DeliveryGroups().current_submitting_group()})

        cls.facilities = [cls.facility, cls.facility2, cls.facility3]
        cls.district_user = bootstrap_user(
            cls.district, username='districtuser', domain=TEST_DOMAIN, home_loc='dis1', phone_number='1234',
            first_name='test', last_name='Test'
        )

        cls.contact1 = bootstrap_user(
            cls.facility, username='contact1', domain=TEST_DOMAIN, home_loc='d10001', phone_number='1235',
            first_name='test', last_name='Test'
        )

        cls.contact2 = bootstrap_user(
            cls.facility2, username='contact2', domain=TEST_DOMAIN, home_loc='d10002', phone_number='1236',
            first_name='test', last_name='Test'
        )

        cls.contact3 = bootstrap_user(
            cls.facility3, username='contact3', domain=TEST_DOMAIN, home_loc='d10003', phone_number='1237',
            first_name='test', last_name='Test'
        )

        for facility in cls.facilities:
            facility.metadata['group'] = cls.relevant_group()
            facility.save()
        create_products(cls, TEST_DOMAIN, ["id", "dp", "fs", "md", "ff", "dx", "bp", "pc", "qi", "jd", "mc", "ip"])

    @classmethod
    def tearDownClass(cls):
        delete_domain_phone_numbers(TEST_DOMAIN)
        cls.domain.delete()
        super(TestReportSummaryBase, cls).tearDownClass()

    def tearDown(self):
        SupplyPointStatus.objects.all().delete()
        super(TestReportSummaryBase, self).tearDown()


class TestDeliverySummary(TestReportSummaryBase):

    @classmethod
    def relevant_group(cls):
        return DeliveryGroups().current_submitting_group()

    def test_basic_report_no_responses(self):
        result = construct_delivery_summary(self.district)
        self.assertEqual(result["total"], 3)
        self.assertEqual(result["not_responding"], 3)
        self.assertEqual(result["not_received"], 0)
        self.assertEqual(result["received"], 0)

    def test_positive_responses(self):
        script = """
            1235 > nimepokea
            1236 > nimepokea
            1237 > nimepokea
        """
        self.run_script(script)
        with mock.patch('custom.ilsgateway.tanzania.reminders.reports.get_business_day_of_month_before',
                        return_value=datetime.utcnow() - timedelta(days=1)):
            result = construct_delivery_summary(self.district)
        self.assertEqual(result["total"], 3)
        self.assertEqual(result["not_responding"], 0)
        self.assertEqual(result["not_received"], 0)
        self.assertEqual(result["received"], 3)

    def test_negative_responses(self):
        script = """
            1235 > sijapokea
            1236 > sijapokea
            1237 > sijapokea
        """
        self.run_script(script)
        with mock.patch('custom.ilsgateway.tanzania.reminders.reports.get_business_day_of_month_before',
                        return_value=datetime.utcnow() - timedelta(days=1)):
            result = construct_delivery_summary(self.district)
        self.assertEqual(result["total"], 3)
        self.assertEqual(result["not_responding"], 0)
        self.assertEqual(result["not_received"], 3)
        self.assertEqual(result["received"], 0)

    def test_overrides(self):
        script = """
            1235 > nimepokea
            1236 > nimepokea
            1237 > nimepokea
        """
        self.run_script(script)

        script = """
            1235 > sijapokea
        """
        self.run_script(script)
        with mock.patch('custom.ilsgateway.tanzania.reminders.reports.get_business_day_of_month_before',
                        return_value=datetime.utcnow() - timedelta(days=1)):
            result = construct_delivery_summary(self.district)
        self.assertEqual(result["total"], 3)
        self.assertEqual(result["not_responding"], 0)
        self.assertEqual(result["not_received"], 1)
        self.assertEqual(result["received"], 2)

    def test_message_initiation(self):
        translation.activate('sw')
        with mock.patch('custom.ilsgateway.tanzania.handlers.messageinitiator.get_business_day_of_month_before',
                        return_value=datetime.utcnow() - timedelta(days=1)):
            script = """
                1234 > test delivery_report TEST DISTRICT
                1234 < %(test_handler_confirm)s
                1234 < %(report_results)s
            """ % {"test_handler_confirm": six.text_type(TEST_HANDLER_CONFIRM),
                   "report_results": six.text_type(REMINDER_MONTHLY_DELIVERY_SUMMARY) % {"received": 0,
                                                                                   "total": 3,
                                                                                   "not_received": 0,
                                                                                   "not_responding": 3}}
            self.run_script(script)

            script = """
                1235 > nimepokea
                1236 > sijapokea
            """
            self.run_script(script)

            script = """
                1234 > test delivery_report TEST DISTRICT
                1234 < %(test_handler_confirm)s
                1234 < %(report_results)s
            """ % {"test_handler_confirm": six.text_type(TEST_HANDLER_CONFIRM),
                   "report_results": six.text_type(REMINDER_MONTHLY_DELIVERY_SUMMARY) % {"received": 1,
                                                                                   "total": 3,
                                                                                   "not_received": 1,
                                                                                   "not_responding": 1}}
            self.run_script(script)


class TestSoHSummary(TestReportSummaryBase):

    @classmethod
    def relevant_group(cls):
        # this doesn't really matter since it's relevant every month
        return DeliveryGroups().current_delivering_group()

    def test_basic_report_no_responses(self):
        result = construct_soh_summary(self.district)
        self.assertEqual(result["total"], 3)
        self.assertEqual(result["not_responding"], 3)
        self.assertEqual(result["submitted"], 0)

    def test_positive_responses(self):
        with mock.patch('custom.ilsgateway.tanzania.reminders.reports.get_business_day_of_month_before',
                        return_value=datetime.utcnow() - timedelta(days=1)):
            script = """
                1235 > Hmk Id 400 Dp 569 Ip 678
                1236 > Hmk Id 400 Dp 569 Ip 678
                1237 > Hmk Id 400 Dp 569 Ip 678
            """
            self.run_script(script)
            result = construct_soh_summary(self.district)
            self.assertEqual(result["total"], 3)
            self.assertEqual(result["not_responding"], 0)
            self.assertEqual(result["submitted"], 3)

    def test_message_initiation(self):
        translation.activate('sw')
        with mock.patch('custom.ilsgateway.tanzania.handlers.messageinitiator.get_business_day_of_month_before',
                        return_value=datetime.utcnow() - timedelta(days=1)):
            script = """
                1234 > test soh_report TEST DISTRICT
                1234 < %(test_handler_confirm)s
                1234 < %(report_results)s
            """ % {"test_handler_confirm": six.text_type(TEST_HANDLER_CONFIRM),
                   "report_results": six.text_type(REMINDER_MONTHLY_SOH_SUMMARY) % {"submitted": 0,
                                                                              "total": 3,
                                                                              "not_responding": 3}}
            self.run_script(script)

            script = """
                1235 > Hmk Id 400 Dp 569 Ip 678
                1236 > Hmk Id 400 Dp 569 Ip 678
            """
            self.run_script(script)

            script = """
                1234 > test soh_report TEST DISTRICT
                1234 < %(test_handler_confirm)s
                1234 < %(report_results)s
            """ % {"test_handler_confirm": six.text_type(TEST_HANDLER_CONFIRM),
                   "report_results": six.text_type(REMINDER_MONTHLY_SOH_SUMMARY) % {"submitted": 2,
                                                                              "total": 3,
                                                                              "not_responding": 1}}
            self.run_script(script)
