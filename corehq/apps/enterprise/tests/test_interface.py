from corehq.apps.accounting.tests import generator
from datetime import datetime
from decimal import Decimal
import math
import uuid

from django.test import TestCase
from django.test.client import RequestFactory

from corehq.messaging.smsbackends.test.models import SQLTestSMSBackend
from corehq.apps.smsbillables.models import SmsBillable, SmsGatewayFee
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.users.models import WebUser
from corehq.apps.sms.models import OUTGOING, SMS

from ..interface import EnterpriseSMSBillablesReport


class TestEnterpriseSMSBillablesReport(TestCase):
    #Tests
    def test_headers(self):
        request = RequestFactory().get('')
        interface = self.create_interface(request)
        test_headers = [['Date of Message', 'Project Space', 'Direction', 'SMS parts', 'Gateway',
            'Gateway Charge', 'Usage Charge', 'Total Charge', 'Message Log ID', 'Is Valid?', 'Date Created']]
        self.assertEqual(interface.headers.as_export_table, test_headers)

    def test_sms_billables_sent_between(self):
        self.create_smsbillable(datetime(2021, 7, 12))
        self.create_smsbillable(datetime(2021, 7, 1))
        self.create_smsbillable(datetime(2021, 5, 5))

        report = self.create_interface(
            date_sent_startdate='2021-06-30',
            date_sent_enddate='2021-07-30'
        )

        results = report.get_all_rows

        self.assertEqual(len(results), 2)

    def test_sms_billables_date_created(self):
        self.create_smsbillable(datetime(2021, 7, 12))
        self.create_smsbillable(datetime(2021, 7, 1))
        self.create_smsbillable(datetime(2021, 5, 5))

        report = self.create_interface(
            report_filter_date_created_use_filter='on',
            date_sent_startdate='2021-06-30',
            date_sent_enddate='2021-07-30',
            date_created_startdate='2021-06-30',
            date_created_enddate='2021-07-30'
        )

        results = report.get_all_rows

        self.assertEqual(len(results), 2)

    def test_sms_billables_show_billables_true(self):
        self.create_smsbillable(datetime(2021, 7, 12), True)
        self.create_smsbillable(datetime(2021, 7, 1), True)
        self.create_smsbillable(datetime(2021, 7, 5), False)

        report = self.create_interface(
            date_sent_startdate='2021-06-30',
            date_sent_enddate='2021-07-30',
            show_billables='valid'
        )

        results = report.get_all_rows

        self.assertEqual(len(results), 2)

    def test_sms_billables_show_billables_false(self):
        self.create_smsbillable(datetime(2021, 7, 12), True)
        self.create_smsbillable(datetime(2021, 7, 1), True)
        self.create_smsbillable(datetime(2021, 7, 5), False)

        report = self.create_interface(
            date_sent_startdate='2021-06-30',
            date_sent_enddate='2021-07-30',
            show_billables='invalid'
        )

        results = report.get_all_rows

        self.assertEqual(len(results), 1)

    def test_sms_billables_has_gateway_fee(self):
        gateway_fee = Decimal('6.9')
        self.create_smsbillable(datetime(2021, 7, 12), True, None)
        self.create_smsbillable(datetime(2021, 7, 1), False, gateway_fee)
        self.create_smsbillable(datetime(2021, 7, 5), False, gateway_fee)

        report = self.create_interface(
            date_sent_startdate='2021-06-30',
            date_sent_enddate='2021-07-30',
            has_gateway_fee='yes'
        )

        results = report.get_all_rows

        self.assertEqual(len(results), 2)

    def test_sms_billables_not_has_gateway_fee(self):
        gateway_fee = Decimal('4.20')
        self.create_smsbillable(datetime(2021, 7, 12), True, None)
        self.create_smsbillable(datetime(2021, 7, 1), False, gateway_fee)
        self.create_smsbillable(datetime(2021, 7, 5), False, gateway_fee)

        report = self.create_interface(
            date_sent_startdate='2021-06-30',
            date_sent_enddate='2021-07-30',
            has_gateway_fee='no'
        )

        results = report.get_all_rows

        self.assertEqual(len(results), 1)

    def test_sms_billables_random_filters(self):
        gateway_fee = Decimal('4.20')
        self.create_smsbillable(datetime(2021, 7, 12), True, None)
        self.create_smsbillable(datetime(2021, 7, 1), True, gateway_fee)
        self.create_smsbillable(datetime(2021, 7, 5), False, gateway_fee)

        report = self.create_interface(
            date_sent_startdate='2021-06-30',
            date_sent_enddate='2021-07-30',
            report_filter_date_created_use_filter='on',
            date_created_startdate='2021-06-30',
            date_created_enddate='2021-07-30',
            has_gateway_fee='no'
        )

        results = report.get_all_rows

        self.assertEqual(len(results), 1)

    #End Tests

    #Set Up
    @classmethod
    def setUpClass(cls):
        super(TestEnterpriseSMSBillablesReport, cls).setUpClass()
        cls.domain = 'test-domain'
        cls.domain_obj = create_domain(cls.domain)
        cls.user = WebUser.create(
            cls.domain,
            "test-user",
            "123",
            None,
            None,
        )

        cls.account = generator.billing_account(cls.user, "null-user@dimagi.com")
        cls.subscription_length = 15  # months
        subscription_start_date = datetime(2021, 1, 1)
        cls.subscription = generator.generate_domain_subscription(
            cls.account,
            cls.domain_obj,
            date_start=subscription_start_date,
            date_end=None
        )
        cls.subscription.is_active = True
        cls.subscription.save()

        cls.backend = SQLTestSMSBackend(
            name="TEST",
            is_global=True,
            domain=cls.domain,
            hq_api_id=SQLTestSMSBackend.get_api_id()
        )
        cls.backend.save()

    @classmethod
    def tearDownClass(cls):
        cls.user.delete(deleted_by=None)
        cls.domain_obj.delete()
        cls.backend.delete()
        super(TestEnterpriseSMSBillablesReport, cls).tearDownClass()

    def setUp(self):
        super(TestEnterpriseSMSBillablesReport, self).setUp()
        self.billable = self.gateway_fee = self.msg = None

    def tearDown(self):
        if self.billable is not None:
            self.billable.delete()
        if self.gateway_fee is not None:
            self.gateway_fee.delete()
        if self.msg is not None:
            self.msg.delete()
        super(TestEnterpriseSMSBillablesReport, self).tearDown()
    #End Set Up

    #Util Methods
    def create_interface(
        self,
        report_filter_date_created_use_filter='off',
        date_sent_startdate='2021-06-30',
        date_sent_enddate='2021-07-30',
        date_created_startdate='2021-06-30',
        date_created_enddate='2021-07-30',
        show_billables='',
        domain='test-domain',
        has_gateway_fee='',
        gateway_type=''
    ):
        request = RequestFactory().get(
            '/test',
            data={
                'report_filter_date_created_use_filter': report_filter_date_created_use_filter,
                'date_sent_startdate': date_sent_startdate,
                'date_sent_enddate': date_sent_enddate,
                'date_created_startdate': date_created_startdate,
                'date_created_enddate': date_created_enddate,
                'show_billables': show_billables,
                'domain': domain,
                'has_gateway_fee': has_gateway_fee,
                'gateway_type': gateway_type
            }
        )
        request.couch_user = self.user
        request.domain = self.domain
        return EnterpriseSMSBillablesReport(request)

    def create_smsbillable(self, date, show_billable=True, gateway_fee=None):
        text = (
            "This is text that will be displayed in a test text message in the "
            "test interface class in Enterprise. I like games and also food. KFC "
            "is actually amazing. I especially like hot food that burns my mouth "
            "I don't know why..."
        )
        self.msg = self.create_fake_sms(self.backend.hq_api_id, self.backend.couch_id, text, date)

        smsbillable = SmsBillable.create(
            self.msg,
            multipart_count=int(math.ceil(len(self.msg.text) / 160)),
        )
        #The is_valid property is queried to display "active" billables
        smsbillable.is_valid = show_billable
        if gateway_fee:
            smsbillable.gateway_fee = SmsGatewayFee.create_new(self.backend.hq_api_id,
                self.msg.direction,
                gateway_fee)
        else:
            smsbillable.gateway_fee = None
        smsbillable.save()

    def create_fake_sms(self, backend_api_id, backend_couch_id, text, date):
        msg = SMS(
            domain=self.domain,
            phone_number='+12223334444',
            direction=OUTGOING,
            date=date,
            backend_api=backend_api_id,
            backend_id=backend_couch_id,
            backend_message_id=uuid.uuid4().hex,
            text=text
        )
        msg.save()
        return msg
    #End Util Methods
