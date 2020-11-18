from django.test import RequestFactory, TestCase, override_settings

import mock

from corehq.apps.accounting.models import (
    BillingAccount,
    DefaultProductPlan,
    SoftwarePlanEdition,
    Subscription,
    SubscriptionAdjustment,
)
from corehq.apps.analytics.utils import (
    get_blocked_hubspot_domains,
    get_blocked_hubspot_email_domains,
    get_blocked_hubspot_accounts,
    is_domain_blocked_from_hubspot,
    is_email_blocked_from_hubspot,
    hubspot_enabled_for_user,
    hubspot_enabled_for_email,
)
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.users.models import WebUser

from ..tasks import (
    HUBSPOT_COOKIE,
    HUBSPOT_SIGNUP_FORM_ID,
    track_web_user_registration_hubspot,
)


@override_settings(ANALYTICS_IDS={'HUBSPOT_API_ID': '1234'})
@mock.patch('corehq.apps.analytics.tasks.requests.get', mock.MagicMock())
@mock.patch('corehq.apps.analytics.tasks.requests.post', mock.MagicMock())
@mock.patch('corehq.apps.analytics.tasks._send_hubspot_form_request')
class TestSendToHubspot(TestCase):
    domain = 'test-send-to-hubspot'

    def test_registration(self, _send_hubspot_form_request):
        request = self.get_request()
        buyer_props = {'buyer_persona': 'Old-Timey Prospector'}
        track_web_user_registration_hubspot(request, self.user, buyer_props)

        _send_hubspot_form_request.assert_called_once()
        hubspot_id, form_id, data = _send_hubspot_form_request.call_args[0]
        self.assertEqual(form_id, HUBSPOT_SIGNUP_FORM_ID)
        self.assertDictContainsSubset(buyer_props, data)

    @classmethod
    def setUpClass(cls):
        super(TestSendToHubspot, cls).setUpClass()
        cls.domain_obj = create_domain(cls.domain)
        cls.user = WebUser.create(cls.domain, "seamus@example.com", "*****", None, None)
        cls.user.save()

    @classmethod
    def tearDownClass(cls):
        cls.domain_obj.delete()
        super(TestSendToHubspot, cls).tearDownClass()

    def get_request(self):
        request = RequestFactory().request()
        request.couch_user = self.user
        request.domain = self.domain
        # The hubspot cookie must be passed from the client
        request.COOKIES[HUBSPOT_COOKIE] = '54321'
        return request


class TestBlockedHubspotData(TestCase):
    blocked_domain = 'block-domain-hubspot'
    allowed_domain = 'allow-domain-hubspot'

    def test_get_blocked_domains(self):
        self.assertEqual(get_blocked_hubspot_domains(), [self.blocked_domain])

    def test_get_blocked_email_domains(self):
        self.assertEqual(get_blocked_hubspot_email_domains(), ['blocked.com'])

    def test_get_blocked_hubspot_accounts(self):
        self.assertEqual(get_blocked_hubspot_accounts(), [
            f'{self.blocked_account.name} - ID # {self.blocked_account.id}',
        ])

    def test_is_domain_blocked_from_hubspot(self):
        self.assertTrue(is_domain_blocked_from_hubspot(self.blocked_domain))
        self.assertFalse(is_domain_blocked_from_hubspot(self.allowed_domain))

    def test_is_email_blocked_from_hubspot(self):
        self.assertTrue(is_email_blocked_from_hubspot(self.blocked_by_email_user.username))
        self.assertFalse(is_email_blocked_from_hubspot(self.allowed_user.username))

    def test_hubspot_enabled_for_user(self):
        self.assertFalse(hubspot_enabled_for_user(self.blocked_by_email_user))
        self.assertFalse(hubspot_enabled_for_user(self.blocked_user))
        self.assertTrue(hubspot_enabled_for_user(self.allowed_user))

    def test_hubspot_enabled_for_email(self):
        self.assertFalse(hubspot_enabled_for_email(self.blocked_by_email_user.username))
        self.assertFalse(hubspot_enabled_for_email(self.blocked_user.username))
        self.assertTrue(hubspot_enabled_for_email(self.allowed_user.username))

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        plan = DefaultProductPlan.get_default_plan_version(edition=SoftwarePlanEdition.ADVANCED)

        cls.blocked_domain_obj = create_domain(cls.blocked_domain)
        cls.blocked_account = BillingAccount.get_or_create_account_by_domain(
            cls.blocked_domain, created_by='test'
        )[0]
        cls.blocked_account.block_hubspot_data_for_all_users = True
        cls.blocked_account.block_email_domains_from_hubspot = ['blocked.com']
        cls.blocked_account.save()
        blocked_sub = Subscription.new_domain_subscription(
            cls.blocked_account, cls.blocked_domain, plan
        )
        blocked_sub.is_active = True
        blocked_sub.save()

        cls.allowed_domain_obj = create_domain(cls.allowed_domain)
        allowed_account = BillingAccount.get_or_create_account_by_domain(
            cls.allowed_domain, created_by='test'
        )[0]
        allowed_sub = Subscription.new_domain_subscription(
            allowed_account, cls.allowed_domain, plan
        )
        allowed_sub.is_active = True
        allowed_sub.save()

        cls.allowed_user = WebUser.create(
            cls.allowed_domain, 'bob@allowed.com', '*****', None, None
        )
        cls.allowed_user.save()

        cls.blocked_by_email_user = WebUser.create(
            cls.allowed_domain, 'jjj@blocked.com', '*****', None, None
        )
        cls.blocked_by_email_user.save()

        cls.blocked_user = WebUser.create(
            cls.blocked_domain, 'fff@example.com', '*****', None, None
        )
        cls.blocked_user.save()

    @classmethod
    def tearDownClass(cls):
        cls.blocked_domain_obj.delete()
        cls.allowed_domain_obj.delete()
        SubscriptionAdjustment.objects.all().delete()
        Subscription.visible_and_suppressed_objects.all().delete()
        BillingAccount.objects.all().delete()
        super().tearDownClass()
