from __future__ import absolute_import
from __future__ import unicode_literals
import uuid
from django.test import TestCase
from django.test.client import RequestFactory

from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.reports.standard.sms import PhoneNumberReport
from corehq.apps.users.models import WebUser
from corehq.apps.sms.models import PhoneNumber


class PhoneNumberReportTestCase(TestCase):
    domain_name = uuid.uuid4().hex

    @classmethod
    def setUpClass(cls):
        super(PhoneNumberReportTestCase, cls).setUpClass()
        cls.domain = create_domain(cls.domain_name)
        cls.couch_user = WebUser.create(None, "phone_report_test", "foobar")
        cls.couch_user.add_domain_membership(cls.domain_name, is_admin=True)
        cls.couch_user.save()

        cls.factory = RequestFactory()

    @classmethod
    def tearDownClass(cls):
        cls.couch_user.delete()
        cls.domain.delete()
        super(PhoneNumberReportTestCase, cls).tearDownClass()

    def add_web_user_phone_number(self, pending_verification=False, verified=False):
        pn = PhoneNumber.objects.create(
            domain=self.domain_name,
            owner_id=self.couch_user.get_id,
            owner_doc_type=self.couch_user.doc_type,
            phone_number='5555555',
            is_two_way=False,
            pending_verification=pending_verification,
            verified=verified,
        )
        self.addCleanup(pn.delete)
        return pn

    def request(self, filter_type='contact', phone_number_filter='',
                has_phone_number='has_phone_number', verification_status='any'):
        request = self.factory.get('/', {
            'filter_type': filter_type,
            'phone_number_filter': phone_number_filter,
            'contact_type': 'users',
            'has_phone_number': has_phone_number,
            'selected_group': '',
            'verification_status': verification_status,
        })
        request.couch_user = self.couch_user
        request.domain = self.domain_name
        return request

    def test_user_with_number(self):
        self.add_web_user_phone_number()
        self.assertEqual(len(list(PhoneNumberReport(self.request(), domain=self.domain_name).rows)), 1)

    def test_user_without_number(self):
        request = self.request()
        self.assertEqual(len(list(PhoneNumberReport(request, domain=self.domain_name).rows)), 0)

        request = self.request(has_phone_number='no_phone_number')
        self.assertEqual(len(list(PhoneNumberReport(request, domain=self.domain_name).rows)), 1)

    def test_unverified_number(self):
        self.add_web_user_phone_number()
        request = self.request(verification_status='not_verified')
        self.assertEqual(len(list(PhoneNumberReport(request, domain=self.domain_name).rows)), 1)

    def test_verified_number(self):
        self.add_web_user_phone_number(verified=True)
        request = self.request(verification_status='verified')
        self.assertEqual(len(list(PhoneNumberReport(request, domain=self.domain_name).rows)), 1)

    def test_verified_pending_number(self):
        self.add_web_user_phone_number(pending_verification=True)
        request = self.request(verification_status='verification_pending')
        self.assertEqual(len(list(PhoneNumberReport(request, domain=self.domain_name).rows)), 1)

    def test_phone_number_filter(self):
        self.add_web_user_phone_number()
        request = self.request(filter_type='phone_number')
        self.assertEqual(len(list(PhoneNumberReport(request, domain=self.domain_name).rows)), 1)
        request = self.request(filter_type='phone_number', phone_number_filter='5555555')
        self.assertEqual(len(list(PhoneNumberReport(request, domain=self.domain_name).rows)), 1)
        request = self.request(filter_type='phone_number', phone_number_filter='123')
        self.assertEqual(len(list(PhoneNumberReport(request, domain=self.domain_name).rows)), 0)

    def test_number_already_in_use(self):
        self.add_web_user_phone_number()
        pn = PhoneNumber.objects.create(
            domain=self.domain_name,
            couch_id='zzzzzzz',  # for deterministic sorting
            owner_id='other_id',
            owner_doc_type='other_doc_type',
            phone_number='5555555',
            is_two_way=True,
            pending_verification=False,
            verified=True,
        )
        self.addCleanup(pn.delete)

        request = self.request(filter_type='phone_number')
        rows = list(PhoneNumberReport(request, domain=self.domain_name).rows)

        self.assertEqual(rows[0][2], 'Already In Use')
        self.assertEqual(rows[1][2], 'Verified')
