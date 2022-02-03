from datetime import datetime

from django.test import RequestFactory, TestCase, override_settings

from unittest import mock

from corehq.apps.accounting.models import (
    DefaultProductPlan,
    SoftwarePlanEdition,
    Subscription,
)
from corehq.apps.accounting.tests import generator
from corehq.apps.analytics.utils.hubspot import (
    get_blocked_hubspot_domains,
    get_blocked_hubspot_accounts,
    is_domain_blocked_from_hubspot,
    hubspot_enabled_for_user,
    hubspot_enabled_for_email,
    emails_that_accepted_invitations_to_blocked_hubspot_domains,
)
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.users.models import (
    WebUser,
    CouchUser,
    CommCareUser,
    Invitation,
)

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

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        plan = DefaultProductPlan.get_default_plan_version(edition=SoftwarePlanEdition.ADVANCED)

        cls.blocked_account = generator.billing_account('test@dimagi.com', 'test@test.com')
        cls.blocked_account.block_hubspot_data_for_all_users = True
        cls.blocked_account.save()

        # this is one domain linked to the billing account that blocks hubspot
        cls.blocked_domain = create_domain('block-domain-hubspot')
        first_blocked_sub = Subscription.new_domain_subscription(
            cls.blocked_account, cls.blocked_domain.name, plan
        )
        first_blocked_sub.is_active = True
        first_blocked_sub.save()

        # this is another domain linked to the billing account that blocks hubspot
        cls.second_blocked_domain = create_domain('block-domain-hubspot-002')
        second_blocked_sub = Subscription.new_domain_subscription(
            cls.blocked_account, cls.second_blocked_domain.name, plan
        )
        second_blocked_sub.is_active = True
        second_blocked_sub.save()

        # this domain is not linked to an account that is blocking hubspot
        cls.allowed_domain = create_domain('allow-domain-hubspot')
        allowed_account = generator.billing_account('test@dimagi.com', 'test@test.com')
        allowed_sub = Subscription.new_domain_subscription(
            allowed_account, cls.allowed_domain.name, plan
        )
        allowed_sub.is_active = True
        allowed_sub.save()

        cls.allowed_user = WebUser.create(
            cls.allowed_domain.name, 'bob@allowed.com', '*****', None, None
        )
        cls.allowed_user.save()

        cls.blocked_user = WebUser.create(
            cls.blocked_domain.name, 'fff@example.com', '*****', None, None
        )
        cls.blocked_user.save()
        cls.blocked_couch_user = CouchUser.get_by_username(cls.blocked_user.username)

        cls.second_blocked_user = WebUser.create(
            cls.second_blocked_domain.name, 'aaa-test@gmail.com', '*****', None, None
        )
        cls.second_blocked_user.save()
        cls.second_blocked_couch_user = CouchUser.get_by_username(
            cls.second_blocked_user.username
        )

        cls.blocked_invitation_user = WebUser.create(
            cls.blocked_domain.name, 'blocked-by-invitation@gmail.com', '*****', None, None
        )
        invite_to_blocked_domain = Invitation(
            email=cls.blocked_invitation_user.username,
            is_accepted=True,
            domain=cls.blocked_domain.name,
            invited_on=datetime.now(),
            invited_by="system@dimagi.com",
        )
        invite_to_blocked_domain.save()

        cls.blocked_commcare_user = CommCareUser.create(
            cls.blocked_domain.name, 'testuser', '****', None, None
        )
        cls.blocked_commcare_user.save()

    def test_get_blocked_domains(self):
        self.assertListEqual(
            get_blocked_hubspot_domains(),
            [self.blocked_domain.name, self.second_blocked_domain.name]
        )

    def test_get_blocked_hubspot_accounts(self):
        self.assertListEqual(get_blocked_hubspot_accounts(), [
            f'{self.blocked_account.name} - ID # {self.blocked_account.id}',
        ])

    def test_is_domain_blocked_from_hubspot(self):
        self.assertTrue(is_domain_blocked_from_hubspot(self.blocked_domain.name))
        self.assertTrue(is_domain_blocked_from_hubspot(self.second_blocked_domain.name))
        self.assertFalse(is_domain_blocked_from_hubspot(self.allowed_domain.name))

    def test_hubspot_enabled_for_user(self):
        self.assertFalse(hubspot_enabled_for_user(self.blocked_user))
        self.assertFalse(hubspot_enabled_for_user(self.second_blocked_user))
        self.assertTrue(hubspot_enabled_for_user(self.allowed_user))

    def test_hubspot_enabled_for_email(self):
        self.assertFalse(hubspot_enabled_for_email(self.blocked_user.username))
        self.assertFalse(hubspot_enabled_for_email(self.second_blocked_user.username))
        self.assertTrue(hubspot_enabled_for_email(self.allowed_user.username))

    def test_removed_user_is_still_blocked(self):
        """
        Ensure that users who have previously accepted an invitation to a domain
        blocking hubspot data, continue to be blocked from hubspot once their
        membership has been removed from that domain.
        """
        self.blocked_invitation_user.delete_domain_membership(self.blocked_domain.name)
        self.blocked_invitation_user.save()
        self.assertFalse(hubspot_enabled_for_email(self.blocked_invitation_user.username))

    def test_emails_that_accepted_invitations_to_blocked_hubspot_domains(self):
        self.assertListEqual(
            [self.blocked_invitation_user.username],
            list(emails_that_accepted_invitations_to_blocked_hubspot_domains())
        )

    def test_couch_user_is_blocked(self):
        """
        Make sure that hubspot_enabled_for_user does not throw an error if a
        CouchUser is passed to it (rather than a WebUser).
        """
        self.assertFalse(hubspot_enabled_for_user(self.blocked_couch_user))

    @classmethod
    def tearDownClass(cls):
        cls.blocked_user.delete(cls.blocked_domain.name, deleted_by=None)
        cls.second_blocked_user.delete(cls.second_blocked_domain.name, deleted_by=None)
        cls.blocked_invitation_user.delete(cls.blocked_domain.name, deleted_by=None)
        cls.allowed_user.delete(cls.allowed_domain.name, deleted_by=None)
        cls.blocked_domain.delete()
        cls.second_blocked_domain.delete()
        cls.allowed_domain.delete()
        super().tearDownClass()
