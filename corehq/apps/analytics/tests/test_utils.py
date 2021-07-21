from django.test import TestCase, RequestFactory, override_settings

from corehq.apps.accounting.models import (
    Subscription,
    DefaultProductPlan,
    SoftwarePlanEdition,
)
from corehq.apps.analytics.utils import is_hubspot_js_allowed_for_request
from corehq.apps.domain.models import Domain
from corehq.apps.accounting.tests import generator as accounting_generator


class TestIsHubspotJsAllowedForRequest(TestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        billing_contact = accounting_generator.create_arbitrary_web_user_name()
        dimagi_user = accounting_generator.create_arbitrary_web_user_name(is_dimagi=True)
        plan = DefaultProductPlan.get_default_plan_version(edition=SoftwarePlanEdition.ADVANCED)

        account_no_hubspot = accounting_generator.billing_account(
            dimagi_user, billing_contact
        )
        account_no_hubspot.block_hubspot_data_for_all_users = True
        account_no_hubspot.save()

        cls.domain_no_hubspot = Domain.get_or_create_with_name(
            "domain-no-hubspot-001",
            is_active=True
        )
        cls.subscription_no_hubspot = Subscription.new_domain_subscription(
            account=account_no_hubspot,
            domain=cls.domain_no_hubspot.name,
            plan_version=plan,
        )

        regular_account = accounting_generator.billing_account(
            dimagi_user, billing_contact
        )
        cls.regular_domain = Domain.get_or_create_with_name(
            "domain-with-analytics-001",
            is_active=True
        )
        cls.regular_subscription = Subscription.new_domain_subscription(
            account=regular_account,
            domain=cls.regular_domain.name,
            plan_version=plan,
        )

    def setUp(self):
        super().setUp()
        self.request = RequestFactory().get('/analytics/test')

    @classmethod
    def tearDownClass(cls):
        cls.domain_no_hubspot.delete()
        cls.regular_domain.delete()
        super().tearDownClass()

    def test_returns_false_if_account_disabled_hubspot(self):
        """
        Ensures that if the BillingAccount associated with a subscription
        has disabled hubspot, is_hubspot_js_allowed_for_request returns False
        """
        self.request.subscription = self.subscription_no_hubspot
        self.assertFalse(is_hubspot_js_allowed_for_request(self.request))

    def test_returns_true_for_normal_subscription(self):
        """
        Ensures that if the BillingAccount associated with a subscription
        has NOT disabled hubspot, is_hubspot_js_allowed_for_request returns True
        """
        self.request.subscription = self.regular_subscription
        self.assertTrue(is_hubspot_js_allowed_for_request(self.request))

    def test_returns_true_if_no_subscription(self):
        """
        Ensures that if no subscription attribute is set on the HttpRequest
        object, is_hubspot_js_allowed_for_request returns True
        """
        self.assertTrue(is_hubspot_js_allowed_for_request(self.request))

    @override_settings(IS_SAAS_ENVIRONMENT=False)
    def test_returns_false_if_not_saas_environment(self):
        """
        Ensures that if the environment is not a SaaS environment,
        is_hubspot_js_allowed_for_request returns False
        """
        self.assertFalse(is_hubspot_js_allowed_for_request(self.request))
