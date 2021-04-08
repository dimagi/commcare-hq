from django.test import TestCase, RequestFactory

from corehq.apps.domain.models import Domain
from corehq.apps.hqwebapp.async_handler import AsyncHandlerError
from corehq.apps.sso.async_handlers import (
    IdentityProviderAdminAsyncHandler,
    SSOExemptUsersAdminAsyncHandler,
)
from corehq.apps.sso.models import (
    IdentityProvider,
    AuthenticatedEmailDomain,
    UserExemptFromSingleSignOn,
)
from corehq.apps.sso.tests import generator


class BaseAsyncHandlerTest(TestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.account = generator.get_billing_account_for_idp()
        cls.domain = Domain.get_or_create_with_name(
            "vaultwax-001",
            is_active=True
        )
        # this Identity Provider will be the main subject of the test
        cls.idp = IdentityProvider.objects.create(
            owner=cls.account,
            name='Azure AD for Vault Wax',
            slug='vaultwax',
            created_by='someadmin@dimagi.com',
            last_modified_by='someadmin@dimagi.com',
        )
        cls.idp.create_service_provider_certificate()

        # secondary Identity Provider to test some edge cases
        cls.other_idp = IdentityProvider.objects.create(
            owner=cls.account,
            name='Azure AD for VWX',
            slug='vwx',
            created_by='someadmin@dimagi.com',
            last_modified_by='someadmin@dimagi.com',
        )
        cls.other_idp.create_service_provider_certificate()

    @classmethod
    def tearDownClass(cls):
        IdentityProvider.objects.all().delete()
        cls.domain.delete()
        cls.account.delete()
        super().tearDownClass()

    def _get_post_data(self, object_name=None):
        """
        The data that will populate request.POST in all the tests below.
        :param object_name: the parameter that will be in POST.objectName
        :return: dict for request.POST
        """
        return {
            'requestContext[idpSlug]': self.idp.slug,
            'objectName': object_name,
        }


class TestIdentityProviderAdminAsyncHandler(BaseAsyncHandlerTest):

    def setUp(self):
        super().setUp()
        self.request = RequestFactory().get('/sso/test')
        self.request.method = 'POST'

    def tearDown(self):
        AuthenticatedEmailDomain.objects.all().delete()
        super().tearDown()

    def test_get_linked_objects(self):
        """
        Ensure that get_linked_objects() returns all AuthenticatedEmailDomains
        associated with a given IdentityProvider.
        """
        AuthenticatedEmailDomain.objects.create(
            identity_provider=self.idp,
            email_domain='vaultwax.com'
        )
        AuthenticatedEmailDomain.objects.create(
            identity_provider=self.idp,
            email_domain='vaultwax.nl'
        )
        self.request.POST = self._get_post_data()
        handler = IdentityProviderAdminAsyncHandler(self.request)
        self.assertEqual(
            handler.get_linked_objects(),
            [
                'vaultwax.com',
                'vaultwax.nl',
            ]
        )

    def test_add_object_raises_error_if_conflict_with_idp(self):
        """
        Ensure that add_object() raises an error if the email domain specified
        in objectName already has an AuthenticatedEmailDomain relationship
        with the IdentityProvider.
        """
        AuthenticatedEmailDomain.objects.create(
            identity_provider=self.idp,
            email_domain='vaultwax.com'
        )
        self.request.POST = self._get_post_data('vaultwax.com')
        handler = IdentityProviderAdminAsyncHandler(self.request)
        with self.assertRaises(AsyncHandlerError):
            handler.add_object()

    def test_add_object_raises_error_if_conflict_with_another_idp(self):
        """
        Ensure that add_object() raises an error if the email domain
        in objectName is already associated with another IdentityProvider.
        """
        AuthenticatedEmailDomain.objects.create(
            identity_provider=self.other_idp,
            email_domain='vwx.link'
        )
        self.request.POST = self._get_post_data('vwx.link')
        handler = IdentityProviderAdminAsyncHandler(self.request)
        with self.assertRaises(AsyncHandlerError):
            handler.add_object()

    def test_add_object_response(self):
        """
        Ensure that add_object_response correctly creates an
        AuthenticatedEmailDomain relationship for the email domain in objectName
        and returns a response that is formatted as expected.
        """
        self.request.POST = self._get_post_data('vaultwax.com')
        handler = IdentityProviderAdminAsyncHandler(self.request)
        self.assertEqual(
            handler.add_object_response,
            {
                'linkedObjects': ['vaultwax.com'],
            }
        )

    def test_remove_object_fails_if_no_email_domain_exists(self):
        """
        Ensure that the remove_object() raises an error when trying to remove
        an email domain which does not have an AuthenticatedEmailDomain
        relationship with any IdentityProvider.
        """
        self.request.POST = self._get_post_data('vaultwax.com')
        handler = IdentityProviderAdminAsyncHandler(self.request)
        with self.assertRaises(AsyncHandlerError):
            handler.remove_object()

    def test_remove_object_fails_if_email_domain_is_related_to_other_idp(self):
        """
        Ensure that remove_object() fails when trying to remove an email domain
        that is related to another IdentityProvider that is not the current
        IdentityProvider.
        """
        AuthenticatedEmailDomain.objects.create(
            identity_provider=self.other_idp,
            email_domain='vwx.link'
        )
        self.request.POST = self._get_post_data('vwx.link')
        handler = IdentityProviderAdminAsyncHandler(self.request)
        with self.assertRaises(AsyncHandlerError):
            handler.remove_object()

    def test_remove_object_removes_email_domain(self):
        """
        Ensure that the remove_object_response successfully removes the
        AuthenticatedEmailDomain relationship with the IdentityProvider and
        returns a response formatted as expected.
        """
        AuthenticatedEmailDomain.objects.create(
            identity_provider=self.idp,
            email_domain='vaultwax.com',
        )
        self.request.POST = self._get_post_data('vaultwax.com')
        handler = IdentityProviderAdminAsyncHandler(self.request)
        self.assertEqual(
            handler.get_linked_objects(),
            ['vaultwax.com']
        )
        self.assertEqual(
            handler.remove_object_response,
            {
                'linkedObjects': [],
            }
        )


class TestSSOExemptUsersAdminAsyncHandler(BaseAsyncHandlerTest):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.email_domain = AuthenticatedEmailDomain.objects.create(
            identity_provider=cls.idp,
            email_domain='vaultwax.com',
        )
        cls.email_domain_secondary = AuthenticatedEmailDomain.objects.create(
            identity_provider=cls.idp,
            email_domain='vaultwax.nl',
        )
        cls.other_email_domain = AuthenticatedEmailDomain.objects.create(
            identity_provider=cls.other_idp,
            email_domain='vwx.link',
        )

    @classmethod
    def tearDownClass(cls):
        AuthenticatedEmailDomain.objects.all().delete()
        super().tearDownClass()

    def setUp(self):
        super().setUp()
        self.request = RequestFactory().get('/sso/test')
        self.request.method = 'POST'
        self.idp.refresh_from_db()

    def tearDown(self):
        UserExemptFromSingleSignOn.objects.all().delete()
        super().tearDown()

    def test_get_linked_objects(self):
        """
        Ensure that all SSO exempt users for a given Identity Provider
        are returned in get_linked_objects().
        """
        UserExemptFromSingleSignOn.objects.create(
            email_domain=self.email_domain,
            username='b@vaultwax.com'
        )
        UserExemptFromSingleSignOn.objects.create(
            email_domain=self.email_domain,
            username='c@vaultwax.com'
        )
        UserExemptFromSingleSignOn.objects.create(
            email_domain=self.email_domain_secondary,
            username='d@vaultwax.nl'
        )
        self.request.POST = self._get_post_data()
        handler = SSOExemptUsersAdminAsyncHandler(self.request)
        self.assertEqual(
            handler.get_linked_objects(),
            [
                'b@vaultwax.com',
                'c@vaultwax.com',
                'd@vaultwax.nl',
            ]
        )

    def test_missing_email_domain_in_username_raises_error(self):
        """
        Ensure that a badly formatted email passed to objectName raises
        an error.
        """
        self.request.POST = self._get_post_data('bademail')
        handler = SSOExemptUsersAdminAsyncHandler(self.request)
        with self.assertRaises(AsyncHandlerError):
            handler.email_domain

    def test_add_object_raises_errors_if_username_exists(self):
        """
        Ensure that add_object() prevents adding duplicate entries.
        """
        UserExemptFromSingleSignOn.objects.create(
            username='b@vaultwax.com',
            email_domain=self.email_domain
        )
        self.request.POST = self._get_post_data('b@vaultwax.com')
        handler = SSOExemptUsersAdminAsyncHandler(self.request)
        with self.assertRaises(AsyncHandlerError):
            handler.add_object()

    def test_add_object_raises_errors_if_email_domain_is_linked_to_different_idp(self):
        """
        Ensure that add_object() prevents adding users whose email domains
        are associated with a different IdentityProvider
        """
        self.request.POST = self._get_post_data('b@vwx.link')
        handler = SSOExemptUsersAdminAsyncHandler(self.request)
        with self.assertRaises(AsyncHandlerError):
            handler.add_object()

    def test_add_object_raises_errors_if_email_domain_does_not_exist(self):
        """
        Ensure that add_object() prevents adding users whose email domains
        are not associated with any IdentityProvider.
        """
        self.request.POST = self._get_post_data('b@dimagi.com')
        handler = SSOExemptUsersAdminAsyncHandler(self.request)
        with self.assertRaises(AsyncHandlerError):
            handler.add_object()

    def test_add_object_response(self):
        """
        Ensure that add_object_response correctly adds the SSO exempt user
        and returns an expected result.
        """
        self.request.POST = self._get_post_data('b@vaultwax.com')
        handler = SSOExemptUsersAdminAsyncHandler(self.request)
        self.assertEqual(
            handler.add_object_response,
            {
                'linkedObjects': ['b@vaultwax.com'],
            }
        )

    def test_remove_object_raises_error_if_username_does_not_exist(self):
        """
        Ensure that remove_object() raises an error if objectName includes a
        user that does not have a UserExemptFromSingleSignOn relationship.
        """
        self.request.POST = self._get_post_data('b@vaultwax.com')
        handler = SSOExemptUsersAdminAsyncHandler(self.request)
        with self.assertRaises(AsyncHandlerError):
            handler.remove_object()

    def test_remove_object_raises_error_if_username_is_not_linked_to_idp(self):
        """
        Ensure that remove_object() raises an error if objectName includes a
        user that belongs to another IdentityProvider that is not the current
        IdentityProvider.
        """
        UserExemptFromSingleSignOn.objects.create(
            username='b@vwx.link',
            email_domain=self.other_email_domain
        )
        self.request.POST = self._get_post_data('b@vwx.link')
        handler = SSOExemptUsersAdminAsyncHandler(self.request)
        with self.assertRaises(AsyncHandlerError):
            handler.remove_object()

    def test_remove_object_raises_error_if_idp_is_editable_and_only_one_username(self):
        """
        Ensure that remove_object() raises an error if the IdentityProvider is
        editable and there is only one UserExemptFromSingleSignOn relationship
        left for that IdentityProvider.
        """
        UserExemptFromSingleSignOn.objects.create(
            username='b@vaultwax.com',
            email_domain=self.email_domain
        )
        self.idp.is_editable = True
        self.idp.save()
        self.request.POST = self._get_post_data('b@vaultwax.com')
        handler = SSOExemptUsersAdminAsyncHandler(self.request)
        with self.assertRaises(AsyncHandlerError):
            handler.remove_object()

    def test_remove_object_response(self):
        """
        Ensure that remove_object_response correctly removes the user specified
        in objectName and returns a response that is formatted as expected.
        """
        UserExemptFromSingleSignOn.objects.create(
            username='b@vaultwax.com',
            email_domain=self.email_domain
        )
        self.request.POST = self._get_post_data('b@vaultwax.com')
        handler = SSOExemptUsersAdminAsyncHandler(self.request)
        self.assertEqual(
            handler.get_linked_objects(),
            ['b@vaultwax.com']
        )
        self.assertEqual(
            handler.remove_object_response,
            {
                'linkedObjects': [],
            }
        )
