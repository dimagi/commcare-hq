from contextlib import contextmanager

from django.contrib.messages.storage import default_storage
from django.core.exceptions import PermissionDenied
from django.test import Client, RequestFactory, TestCase
from django.urls import reverse

import pytest
from django_prbac.models import Role
from unmagic import fixture, use

from corehq import privileges
from corehq.apps.accounting.models import (
    BillingAccount,
    DefaultProductPlan,
    SoftwarePlanEdition,
    Subscription,
)
from corehq.apps.domain.models import Domain
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.sms.views import AddDomainGatewayView, enable_messaging
from corehq.apps.users.models import WebUser
from corehq.messaging.smsbackends.telerivet.models import SQLTelerivetBackend
from corehq.messaging.smsbackends.twilio.models import SQLTwilioBackend
from corehq.util.test_utils import flag_enabled

DOMAIN_NAME = 'test-domain'
USERNAME = "terry"
PASSWORD = "sp@m_sp4m-spAm!"
ADMIN_USER = "admin@example.com"


class GatewayViewTests(TestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.project = create_domain(DOMAIN_NAME)

        account, __ = BillingAccount.get_or_create_account_by_domain(
            DOMAIN_NAME, created_by=ADMIN_USER
        )
        plan = DefaultProductPlan.get_default_plan_version(
            edition=SoftwarePlanEdition.ADVANCED
        )
        Subscription.new_domain_subscription(
            account,
            DOMAIN_NAME,
            plan,
            web_user=ADMIN_USER,
        )

    def setUp(self):
        self.client = Client()
        self.twilio_url = reverse(AddDomainGatewayView.urlname, kwargs={
            'domain': DOMAIN_NAME,
            'hq_api_id': SQLTwilioBackend.get_api_id()
        })
        self.telerivet_url = reverse(AddDomainGatewayView.urlname, kwargs={
            'domain': DOMAIN_NAME,
            'hq_api_id': SQLTelerivetBackend.get_api_id()
        })

    @classmethod
    def tearDownClass(cls):
        cls.project.delete()
        super().tearDownClass()

    def test_superuser(self):
        """
        Superusers can add Twilio gateways
        """
        with superuser():
            self.client.login(username=USERNAME, password=PASSWORD)
            response = self.client.get(self.twilio_url)
            page_name = response.context['page']['page_name']
            self.assertEqual(page_name, 'Add Twilio Gateway')

    def test_contractor(self):
        """
        Contractors can add Twilio gateways
        """
        with contractor():
            self.client.login(username=USERNAME, password=PASSWORD)
            response = self.client.get(self.twilio_url)
            page_name = response.context['page']['page_name']
            self.assertEqual(page_name, 'Add Twilio Gateway')

    def test_domain_admin_twilio(self):
        """
        Domain admins can't add Twilio gateways
        """
        with domain_admin():
            self.client.login(username=USERNAME, password=PASSWORD)
            response = self.client.get(self.twilio_url)
            self.assertEqual(response.status_code, 404)

    def test_domain_admin_telerivet(self):
        """
        Domain admins can add Telerivet gateways
        """
        with domain_admin():
            self.client.login(username=USERNAME, password=PASSWORD)
            response = self.client.get(self.telerivet_url)
            page_name = response.context['page']['page_name']
            self.assertEqual(page_name, 'Add Telerivet (Android) Gateway')

    def test_normal_user(self):
        """
        Normal users are redirected
        """
        with normal_user():
            self.client.login(username=USERNAME, password=PASSWORD)
            response = self.client.get(self.twilio_url)
            self.assertEqual(response.status_code, 302)


@contextmanager
def normal_user():
    user = WebUser.create(DOMAIN_NAME, USERNAME, PASSWORD, None, None)
    try:
        yield user
    finally:
        user.delete(DOMAIN_NAME, deleted_by=None)


@contextmanager
def domain_admin():
    user = WebUser.create(DOMAIN_NAME, USERNAME, PASSWORD, None, None)
    user.add_domain_membership(DOMAIN_NAME, is_admin=True)
    user.set_role(DOMAIN_NAME, "admin")
    user.save()
    try:
        yield user
    finally:
        user.delete(DOMAIN_NAME, deleted_by=None)


@contextmanager
def contractor():
    with domain_admin(), flag_enabled('IS_CONTRACTOR'):
        yield


@contextmanager
def superuser():
    user = WebUser.create(DOMAIN_NAME, USERNAME, PASSWORD, None, None, is_superuser=True)
    try:
        yield
    finally:
        user.delete(DOMAIN_NAME, deleted_by=None)


@use('db')
@fixture
def messaging_domain():
    domain_obj = create_domain(DOMAIN_NAME)
    yield domain_obj
    domain_obj.delete()


@use(messaging_domain)
class TestEnableMessaging:

    def test_enable_messaging(self):
        with domain_admin() as user:
            enable_messaging(self._request(user), DOMAIN_NAME)

        assert Domain.get_by_name(DOMAIN_NAME).granted_messaging_access

    def test_requires_edit_billing(self):
        with normal_user() as user, pytest.raises(PermissionDenied):
            enable_messaging(self._request(user), DOMAIN_NAME)

    def _request(self, user):
        request = RequestFactory().post('/')
        request.user = user.get_django_user()
        request.domain = DOMAIN_NAME
        request.role = Role.objects.get(slug=privileges.OUTBOUND_SMS)
        request._messages = default_storage(request)
        return request
