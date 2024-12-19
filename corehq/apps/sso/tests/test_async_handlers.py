from django.http import Http404
from django.test import TestCase, RequestFactory

from corehq.apps.domain.models import Domain
from corehq.apps.hqwebapp.async_handler import AsyncHandlerError
from corehq.apps.sso.async_handlers import (
    IdentityProviderAdminAsyncHandler,
    SSOExemptUsersAdminAsyncHandler,
    SsoTestUserAdminAsyncHandler,
)
from corehq.apps.sso.models import (
    IdentityProvider,
    AuthenticatedEmailDomain,
    UserExemptFromSingleSignOn,
    SsoTestUser,
)
from corehq.apps.sso.tests import generator


class FakeSuperuser:
    def __init__(self, is_superuser):
        self.is_superuser = is_superuser


def _get_request(account, is_superuser=False):
    request = RequestFactory().get('/sso/test')
    request.account = account
    request.method = 'POST'
    request.user = FakeSuperuser(is_superuser)
    return request


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
            name='Entra ID for Vault Wax',
            slug='vaultwax',
            created_by='someadmin@dimagi.com',
            last_modified_by='someadmin@dimagi.com',
        )
        cls.idp.create_service_provider_certificate()

        # secondary Identity Provider to test some edge cases
        cls.other_idp = IdentityProvider.objects.create(
            owner=cls.account,
            name='Entra ID for VWX',
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


class TestAsyncHandlerSecurity(BaseAsyncHandlerTest):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.second_account = generator.get_billing_account_for_idp()

    def setUp(self):
        super().setUp()
        self.request = _get_request(self.second_account)
        self.request_superuser = _get_request(self.second_account, is_superuser=True)

    def test_get_linked_objects_response_throws_404(self):
        self.request.POST = self._get_post_data()
        handler = IdentityProviderAdminAsyncHandler(self.request)
        with self.assertRaises(Http404):
            handler.get_linked_objects_response

    def test_add_object_response_throws_404(self):
        self.request.POST = self._get_post_data('vaultwax.nl')
        handler = IdentityProviderAdminAsyncHandler(self.request)
        with self.assertRaises(Http404):
            handler.add_object_response

    def test_remove_object_response_throws_404(self):
        self.request.POST = self._get_post_data('vaultwax.nl')
        handler = IdentityProviderAdminAsyncHandler(self.request)
        with self.assertRaises(Http404):
            handler.remove_object_response

    def test_get_linked_objects_response_does_not_throw_404_for_superusers(self):
        self.request_superuser.POST = self._get_post_data()
        handler = IdentityProviderAdminAsyncHandler(self.request_superuser)
        self.assertEqual(
            handler.get_linked_objects_response,
            {'linkedObjects': []}
        )

    def test_add_object_response_does_not_throw_404_for_superusers(self):
        self.request_superuser.POST = self._get_post_data('vaultwax.nl')
        handler = IdentityProviderAdminAsyncHandler(self.request_superuser)
        self.assertEqual(
            handler.add_object_response,
            {'linkedObjects': ['vaultwax.nl']}
        )

    def test_remove_object_response_does_not_throw_404_for_superusers(self):
        AuthenticatedEmailDomain.objects.create(
            identity_provider=self.idp,
            email_domain='vaultwax.nl'
        )
        self.request_superuser.POST = self._get_post_data('vaultwax.nl')
        handler = IdentityProviderAdminAsyncHandler(self.request_superuser)
        self.assertEqual(
            handler.remove_object_response,
            {'linkedObjects': []}
        )


class TestIdentityProviderAdminAsyncHandler(BaseAsyncHandlerTest):

    def setUp(self):
        super().setUp()
        self.request = _get_request(self.idp.owner)

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
        cls.existing_test_user = SsoTestUser.objects.create(
            username='existingtest@vaultwax.com',
            email_domain=cls.email_domain,
        )

    @classmethod
    def tearDownClass(cls):
        AuthenticatedEmailDomain.objects.all().delete()
        super().tearDownClass()

    def setUp(self):
        super().setUp()
        self.request = _get_request(self.idp.owner)
        self.idp.refresh_from_db()

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

    def test_add_object_raises_errors_there_is_an_existing_test_user(self):
        """
        Ensure that add_object() prevents adding users who are already SSO Test Users.
        """
        self.request.POST = self._get_post_data(self.existing_test_user.username)
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


class TestSsoTestUserAdminAsyncHandler(BaseAsyncHandlerTest):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.email_domain = AuthenticatedEmailDomain.objects.create(
            identity_provider=cls.idp,
            email_domain='dimagi.com',
        )
        cls.email_domain_secondary = AuthenticatedEmailDomain.objects.create(
            identity_provider=cls.idp,
            email_domain='dimagi.org',
        )
        cls.other_email_domain = AuthenticatedEmailDomain.objects.create(
            identity_provider=cls.other_idp,
            email_domain='dima.gi',
        )
        cls.existing_exempt_user = UserExemptFromSingleSignOn.objects.create(
            username='existingexempt@dimagi.com',
            email_domain=cls.email_domain,
        )

    @classmethod
    def tearDownClass(cls):
        AuthenticatedEmailDomain.objects.all().delete()
        super().tearDownClass()

    def setUp(self):
        super().setUp()
        self.request = _get_request(self.idp.owner)
        self.idp.refresh_from_db()

    def test_get_linked_objects(self):
        """
        Ensure that all SSO test users for a given Identity Provider
        are returned in get_linked_objects().
        """
        SsoTestUser.objects.create(
            email_domain=self.email_domain,
            username='a@dimagi.com'
        )
        SsoTestUser.objects.create(
            email_domain=self.email_domain,
            username='b@dimagi.com'
        )
        SsoTestUser.objects.create(
            email_domain=self.email_domain_secondary,
            username='c@dimagi.org'
        )
        self.request.POST = self._get_post_data()
        handler = SsoTestUserAdminAsyncHandler(self.request)
        self.assertEqual(
            handler.get_linked_objects(),
            [
                'a@dimagi.com',
                'b@dimagi.com',
                'c@dimagi.org',
            ]
        )

    def test_missing_email_domain_in_username_raises_error(self):
        """
        Ensure that a badly formatted email passed to objectName raises
        an error.
        """
        self.request.POST = self._get_post_data('bademail')
        handler = SsoTestUserAdminAsyncHandler(self.request)
        with self.assertRaises(AsyncHandlerError):
            handler.email_domain

    def test_add_object_raises_errors_if_username_exists(self):
        """
        Ensure that add_object() prevents adding duplicate entries.
        """
        SsoTestUser.objects.create(
            username='b@dimagi.com',
            email_domain=self.email_domain
        )
        self.request.POST = self._get_post_data('b@dimagi.com')
        handler = SsoTestUserAdminAsyncHandler(self.request)
        with self.assertRaises(AsyncHandlerError):
            handler.add_object()

    def test_add_object_raises_errors_if_email_domain_is_linked_to_different_idp(self):
        """
        Ensure that add_object() prevents adding users whose email domains
        are associated with a different IdentityProvider
        """
        self.request.POST = self._get_post_data('foo@dima.gi')
        handler = SsoTestUserAdminAsyncHandler(self.request)
        with self.assertRaises(AsyncHandlerError):
            handler.add_object()

    def test_add_object_raises_errors_if_email_domain_does_not_exist(self):
        """
        Ensure that add_object() prevents adding users whose email domains
        are not associated with any IdentityProvider.
        """
        self.request.POST = self._get_post_data('b@vaultwax.com')
        handler = SsoTestUserAdminAsyncHandler(self.request)
        with self.assertRaises(AsyncHandlerError):
            handler.add_object()

    def test_add_object_raises_errors_there_is_an_existing_exempt_user(self):
        """
        Ensure that add_object() prevents adding users who are already exempt from SSO
        """
        self.request.POST = self._get_post_data(self.existing_exempt_user.username)
        handler = SsoTestUserAdminAsyncHandler(self.request)
        with self.assertRaises(AsyncHandlerError):
            handler.add_object()

    def test_add_object_response(self):
        """
        Ensure that add_object_response correctly adds the SSO test user
        and returns an expected result.
        """
        self.request.POST = self._get_post_data('b@dimagi.com')
        handler = SsoTestUserAdminAsyncHandler(self.request)
        self.assertEqual(
            handler.add_object_response,
            {
                'linkedObjects': ['b@dimagi.com'],
            }
        )

    def test_remove_object_raises_error_if_username_does_not_exist(self):
        """
        Ensure that remove_object() raises an error if objectName includes a
        user that does not have a SsoTestUser relationship.
        """
        self.request.POST = self._get_post_data('b@dimagi.com')
        handler = SsoTestUserAdminAsyncHandler(self.request)
        with self.assertRaises(AsyncHandlerError):
            handler.remove_object()

    def test_remove_object_raises_error_if_username_is_not_linked_to_idp(self):
        """
        Ensure that remove_object() raises an error if objectName includes a
        user that belongs to another IdentityProvider that is not the current
        IdentityProvider.
        """
        SsoTestUser.objects.create(
            username='b@dima.gi',
            email_domain=self.other_email_domain
        )
        self.request.POST = self._get_post_data('b@vwx.link')
        handler = SsoTestUserAdminAsyncHandler(self.request)
        with self.assertRaises(AsyncHandlerError):
            handler.remove_object()

    def test_remove_object_response(self):
        """
        Ensure that remove_object_response correctly removes the user specified
        in objectName and returns a response that is formatted as expected.
        """
        SsoTestUser.objects.create(
            username='b@dimagi.com',
            email_domain=self.email_domain
        )
        self.request.POST = self._get_post_data('b@dimagi.com')
        handler = SsoTestUserAdminAsyncHandler(self.request)
        self.assertEqual(
            handler.get_linked_objects(),
            ['b@dimagi.com']
        )
        self.assertEqual(
            handler.remove_object_response,
            {
                'linkedObjects': [],
            }
        )
