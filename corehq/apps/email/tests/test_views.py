from contextlib import contextmanager

from django.test import Client, TestCase
from django.urls import reverse

from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.email.views import AddDomainEmailGatewayView
from corehq.apps.users.models import WebUser
from corehq.messaging.emailbackends.aws.models import AWSBackend
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

        # account, __ = BillingAccount.get_or_create_account_by_domain(
        #     DOMAIN_NAME, created_by=ADMIN_USER
        # )
        # plan = DefaultProductPlan.get_default_plan_version(
        #     edition=SoftwarePlanEdition.ADVANCED
        # )
        # Subscription.new_domain_subscription(
        #     account,
        #     DOMAIN_NAME,
        #     plan,
        #     web_user=ADMIN_USER,
        # )

    def setUp(self):
        self.client = Client()
        self.aws_url = reverse(AddDomainEmailGatewayView.urlname, kwargs={
            'domain': DOMAIN_NAME,
            'hq_api_id': AWSBackend.get_api_id()
        })

    @classmethod
    def tearDownClass(cls):
        cls.project.delete()
        super().tearDownClass()

    @flag_enabled('CUSTOM_EMAIL_GATEWAY')
    def test_domain_admin_aws(self):
        """
        Domain admins can access AWS add gateway view
        """
        with domain_admin():
            self.client.login(username=USERNAME, password=PASSWORD)
            response = self.client.get(self.aws_url)
            print(response)
            self.assertEqual(response.status_code, 200)

    @flag_enabled('CUSTOM_EMAIL_GATEWAY')
    def test_normal_user_aws(self):
        """
        Normal user is unable to access add gateway view
        """
        with normal_user():
            self.client.login(username=USERNAME, password=PASSWORD)
            response = self.client.get(self.aws_url)
            self.assertEqual(response.status_code, 302)


@contextmanager
def normal_user():
    user = WebUser.create(DOMAIN_NAME, USERNAME, PASSWORD, None, None)
    try:
        yield
    finally:
        user.delete(DOMAIN_NAME, deleted_by=None)


@contextmanager
def domain_admin():
    user = WebUser.create(DOMAIN_NAME, USERNAME, PASSWORD, None, None)
    user.add_domain_membership(DOMAIN_NAME, is_admin=True)
    user.set_role(DOMAIN_NAME, "admin")
    user.save()
    try:
        yield
    finally:
        user.delete(DOMAIN_NAME, deleted_by=None)
