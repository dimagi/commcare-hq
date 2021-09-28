from testil import eq

from django.contrib.messages.middleware import MessageMiddleware
from django.contrib.messages import get_messages
from django.test import TestCase, RequestFactory, override_settings

from corehq.apps.accounting.models import Subscription
from corehq.apps.domain.models import Domain
from corehq.apps.sso.exceptions import SingleSignOnError
from corehq.apps.sso.models import (
    AuthenticatedEmailDomain,
    IdentityProvider,
    TrustedIdentityProvider,
)
from corehq.apps.sso.utils.message_helpers import (
    get_success_message_for_trusted_idp,
)
from corehq.apps.sso.utils.request_helpers import (
    get_request_data,
    is_request_using_sso,
    is_request_blocked_from_viewing_domain_due_to_sso,
)
from corehq.apps.users.models import WebUser
from corehq.apps.sso.tests import generator


@override_settings(SAML2_DEBUG=False)
def test_get_request_data():
    request = RequestFactory().get('/sso/test')
    request.META = {
        'HTTP_HOST': 'test.org',
        'PATH_INFO': '/sso/test',
        'SERVER_PORT': '999',
    }
    request.POST = {
        'post_data': 'test',
    }
    request.GET = {
        'get_data': 'test',
    }
    eq(
        get_request_data(request),
        {
            'https': 'on',
            'http_host': 'test.org',
            'script_name': '/sso/test',
            'server_port': '443',
            'get_data': {
                'get_data': 'test',
            },
            'post_data': {
                'post_data': 'test',
            }
        }
    )


def test_is_request_using_sso_true():
    """
    Testing the successful criteria for an sso request.
    """
    request = RequestFactory().get('/sso/test')
    generator.create_request_session(request, use_sso=True)
    eq(is_request_using_sso(request), True)


def test_is_request_using_sso_false_with_session():
    """
    Testing the usual case for non-sso requests.
    """
    request = RequestFactory().get('/sso/test')
    generator.create_request_session(request)
    eq(is_request_using_sso(request), False)


def test_is_request_using_sso_false_without_session():
    """
    Make sure this call is safe even when session is missing from the request.
    """
    request = RequestFactory().get('/sso/test')
    eq(is_request_using_sso(request), False)


class TestIsRequestBlockedFromViewingDomainDueToSso(TestCase):
    """
    This test verifies what criteria must be met to block an SSO logged in
    User from viewing a Domain.
    """
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.account = generator.get_billing_account_for_idp()
        cls.domain = Domain.get_or_create_with_name(
            "helping-earth-001",
            is_active=True
        )
        enterprise_plan = generator.get_enterprise_plan()
        Subscription.new_domain_subscription(
            account=cls.account,
            domain=cls.domain.name,
            plan_version=enterprise_plan,
        )
        cls.user = WebUser.create(
            cls.domain.name, 'jorge@helpingearth.org', 'testpwd', None, None
        )
        cls.idp = generator.create_idp('helping-earth', cls.account)
        cls.idp.is_active = True
        cls.idp.save()
        AuthenticatedEmailDomain.objects.create(
            email_domain='helpingearth.org',
            identity_provider=cls.idp,
        )

        cls.domain_created_by_user = Domain.get_or_create_with_name(
            "my-test-project",
            is_active=True
        )
        cls.domain_created_by_user.creating_user = cls.user.username
        cls.domain_created_by_user.save()

        cls.external_domain = Domain.get_or_create_with_name(
            "vaultwax-001",
            is_active=True
        )
        cls.user_without_idp = WebUser.create(
            cls.external_domain.name, 'b@vaultwax.com', 'testpwd', None, None
        )

    @classmethod
    def tearDownClass(cls):
        AuthenticatedEmailDomain.objects.all().delete()
        IdentityProvider.objects.all().delete()
        cls.user_without_idp.delete(cls.external_domain.name, deleted_by=None)
        cls.user.delete(cls.domain.name, deleted_by=None)
        cls.domain_created_by_user.delete()
        cls.external_domain.delete()
        cls.domain.delete()
        super().tearDownClass()

    def setUp(self):
        super().setUp()
        self.request = RequestFactory().get('/sso/test')
        generator.create_request_session(self.request, use_sso=True)
        MessageMiddleware().process_request(self.request)  # add support for messages
        self.request.user = self.user

    def tearDown(self):
        TrustedIdentityProvider.objects.all().delete()
        super().tearDown()

    def test_returns_false_if_request_is_not_using_sso(self):
        """
        A request not using SSO should never be blocked by SSO requirements.
        """
        request = RequestFactory().get('/sso/test')
        self.assertFalse(
            is_request_blocked_from_viewing_domain_due_to_sso(
                request,
                self.domain
            )
        )
        request.session = {}
        self.assertFalse(
            is_request_blocked_from_viewing_domain_due_to_sso(
                request,
                self.domain
            )
        )

    def test_raises_error_if_request_uses_sso_but_user_does_not_have_idp(self):
        """
        This should never be a state that we get into, and if we do there
        is something seriously wrong that we need to look into ASAP.

        `is_request_blocked_from_viewing_domain_due_to_sso` should raise
        a `SingleSignOnError` if the request meets sso requirements, but the
        signed in user does not map to an Identity Provider.
        """
        self.request.user = self.user_without_idp
        with self.assertRaises(SingleSignOnError):
            self.assertFalse(
                is_request_blocked_from_viewing_domain_due_to_sso(
                    self.request,
                    self.domain
                )
            )

    def test_returns_false_if_domain_belongs_to_idp_account_owner(self):
        """
        If a domain has an active subscription owned by the account that
        owns the Identity Provider the user has signed in with, the request
        should not be blocked.
        """
        self.assertFalse(
            is_request_blocked_from_viewing_domain_due_to_sso(
                self.request,
                self.domain
            )
        )

    def test_returns_false_if_domain_trusts_identity_provider(self):
        """
        If a domain trusts the Identity Provider that the requesting user is
        signed in with, the request should not be blocked.
        """
        TrustedIdentityProvider.objects.create(
            domain=self.external_domain.name,
            identity_provider=self.idp,
            acknowledged_by='b@hrs.org'
        )
        self.assertFalse(
            is_request_blocked_from_viewing_domain_due_to_sso(
                self.request,
                self.external_domain
            )
        )

    def test_auto_trust_for_domains_created_by_user(self):
        """
        If a user is the creating_user of a domain, then their request should
        not be blocked. A TrustedIdentityProvider relationship should
        automatically be created between the domain and the user's
        Identity Provider. Additionally, a success message should then
        be added through django messages informing the user that the
        domain now trusts the Identity Provider.
        """
        # check that no trust exists yet
        self.assertFalse(
            TrustedIdentityProvider.objects.filter(
                domain=self.domain_created_by_user.name,
                identity_provider=self.idp,
            ).exists()
        )

        # check that the request is not blocked for a domain created by a user
        self.assertFalse(
            is_request_blocked_from_viewing_domain_due_to_sso(
                self.request,
                self.domain_created_by_user
            )
        )

        # check that a trust now exists
        trust = TrustedIdentityProvider.objects.get(
            domain=self.domain_created_by_user.name,
            identity_provider=self.idp,
        )
        self.assertTrue(trust.acknowledged_by, self.user.username)

        # and that the request is still not blocked
        self.assertFalse(
            is_request_blocked_from_viewing_domain_due_to_sso(
                self.request,
                self.domain_created_by_user
            )
        )

        # check that the catch comes from does_domain_trust_this_idp
        self.assertTrue(self.idp.does_domain_trust_this_idp(
            self.domain_created_by_user.name
        ))

        # also check that a message was added to the request
        messages = list(get_messages(self.request))
        self.assertEqual(
            str(messages[0]),
            get_success_message_for_trusted_idp(
                self.idp,
                self.domain_created_by_user
            )
        )

    def test_returns_true_if_external_domain_does_not_trust_idp(self):
        """
        If a domain not belonging to the Identity Provider owner does not
        trust the Identity Provider, and the user is logged in with sso
        under that Identity Provider, their request should be blocked.
        """
        self.assertTrue(
            is_request_blocked_from_viewing_domain_due_to_sso(
                self.request,
                self.external_domain
            )
        )
