from contextlib import contextmanager

from django.test import Client, TestCase
from django.urls import reverse

from corehq.apps.accounting.models import (
    BillingAccount,
    DefaultProductPlan,
    SoftwarePlanEdition,
    Subscription,
)
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.sms.views import AddDomainGatewayView
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
    user = WebUser.create(DOMAIN_NAME, USERNAME, PASSWORD)
    try:
        yield
    finally:
        user.delete()


@contextmanager
def domain_admin():
    user = WebUser.create(DOMAIN_NAME, USERNAME, PASSWORD)
    user.add_domain_membership(DOMAIN_NAME, is_admin=True)
    user.set_role(DOMAIN_NAME, "admin")
    user.save()
    try:
        yield
    finally:
        user.delete()


@contextmanager
def contractor():
    with domain_admin(), flag_enabled('IS_CONTRACTOR'):
        yield


@contextmanager
def superuser():
    user = WebUser.create(DOMAIN_NAME, USERNAME, PASSWORD, is_superuser=True)
    try:
        yield
    finally:
        user.delete()
