from datetime import datetime
from unittest.mock import patch

from django.contrib.auth.models import User
from django.http.request import HttpRequest
from django.test import SimpleTestCase, TestCase

from freezegun import freeze_time

from corehq.apps.domain.auth import (
    ApiKeyFallbackBackend,
    HQApiKeyAuthentication,
    user_can_access_domain_specific_pages,
)
from corehq.apps.domain.models import Domain
from corehq.apps.users.models import CouchUser, HQApiKey


class TestUserCanAccessDomainSpecificPages(SimpleTestCase):
    def test_request_with_no_logged_in_user(self, *args):
        request = HttpRequest()

        with patch('corehq.apps.domain.decorators.active_user_logged_in', return_value=False):
            self.assertFalse(user_can_access_domain_specific_pages(request))

    @patch('corehq.apps.domain.decorators.active_user_logged_in', return_value=True)
    def test_request_with_no_project(self, *args):
        request = HttpRequest()

        with patch('corehq.apps.domain.decorators._ensure_request_project', return_value=None):
            self.assertFalse(user_can_access_domain_specific_pages(request))

    @patch('corehq.apps.domain.decorators.active_user_logged_in', return_value=True)
    def test_request_with_inactive_project(self, *args):
        request = HttpRequest()
        project = Domain(is_active=False)

        with patch('corehq.apps.domain.decorators._ensure_request_project', return_value=project):
            self.assertFalse(user_can_access_domain_specific_pages(request))

    @patch('corehq.apps.domain.decorators.active_user_logged_in', return_value=True)
    @patch('corehq.apps.domain.decorators._ensure_request_project', return_value=Domain(is_active=True))
    def test_request_with_no_couch_user(self, *args):
        request = HttpRequest()

        self.assertFalse(user_can_access_domain_specific_pages(request))

    @patch('corehq.apps.domain.decorators.active_user_logged_in', return_value=True)
    @patch('corehq.apps.domain.decorators._ensure_request_project', return_value=Domain(is_active=True))
    @patch('corehq.apps.domain.decorators._ensure_request_couch_user', return_value=CouchUser())
    def test_request_for_missing_domain_membership_for_non_superuser(self, *args):
        request = HttpRequest()

        self.assertFalse(user_can_access_domain_specific_pages(request))

    @patch('corehq.apps.domain.decorators.active_user_logged_in', return_value=True)
    @patch('corehq.apps.domain.decorators._ensure_request_project', return_value=Domain(is_active=True))
    def test_request_for_missing_domain_membership_for_superuser(self, *args):
        request = HttpRequest()

        couch_user = CouchUser()
        couch_user.is_superuser = True

        with patch('corehq.apps.domain.decorators._ensure_request_couch_user', return_value=couch_user):
            self.assertTrue(user_can_access_domain_specific_pages(request))

    @patch('corehq.apps.domain.decorators.active_user_logged_in', return_value=True)
    @patch('corehq.apps.domain.decorators._ensure_request_project', return_value=Domain(is_active=True))
    @patch('corehq.apps.domain.decorators._ensure_request_couch_user', return_value=CouchUser())
    def test_request_for_valid_domain_membership_for_non_superuser(self, *args):
        request = HttpRequest()

        with patch('corehq.apps.users.models.CouchUser.is_member_of', return_value=True):
            self.assertTrue(user_can_access_domain_specific_pages(request))


class ApiKeyFallbackTests(TestCase):
    def test_fails_if_does_not_allow_api_keys_as_passwords(self):
        user = self._create_user('test@dimagi.com')
        self._create_api_key_for_user(user, key='1234')

        request = self._create_request(can_use_api_key=False)

        self.assertIsNone(self.backend.authenticate(request, 'test@dimagi.com', '1234'))

    def test_returns_user_on_successful_auth(self):
        user = self._create_user('test@dimagi.com')
        self._create_api_key_for_user(user, key='1234')

        request = self._create_request()

        self.assertEqual(self.backend.authenticate(request, 'test@dimagi.com', '1234'), user)

    def test_does_not_authenticate_against_inactive_keys(self):
        user = self._create_user('test@dimagi.com')
        self._create_api_key_for_user(user, key='1234', is_active=False)

        request = self._create_request()

        self.assertIsNone(self.backend.authenticate(request, 'test@dimagi.com', '1234'))

    def test_allows_access_via_domain_restricted_keys(self):
        user = self._create_user('test@dimagi.com')
        self._create_api_key_for_user(user, key='1234', domain='test-domain')

        request = self._create_request(for_domain='test-domain')

        self.assertEqual(self.backend.authenticate(request, 'test@dimagi.com', '1234'), user)

    def test_does_not_allow_cross_domain_access(self):
        user = self._create_user('test@dimagi.com')
        self._create_api_key_for_user(user, key='1234', domain='test-domain1')

        request = self._create_request(for_domain='test-domain2')

        self.assertIsNone(self.backend.authenticate(request, 'test@dimagi.com', '1234'))

    def test_allows_access_to_ips_on_whitelist(self):
        user = self._create_user('test@dimagi.com')
        self._create_api_key_for_user(user, key='1234', allowed_ips=['127.0.0.1'])

        request = self._create_request(ip='127.0.0.1')

        self.assertEqual(self.backend.authenticate(request, 'test@dimagi.com', '1234'), user)

    def test_does_not_allow_ips_not_on_whitelist(self):
        user = self._create_user('test@dimagi.com')
        self._create_api_key_for_user(user, key='1234', allowed_ips=['127.0.0.1'])

        request = self._create_request(ip='5.5.5.5')

        self.assertIsNone(self.backend.authenticate(request, 'test@dimagi.com', '1234'))

    def test_allows_empty_ip_for_non_ip_restrictive_keys(self):
        user = self._create_user('test@dimagi.com')
        self._create_api_key_for_user(user, key='1234', allowed_ips=[])

        request = self._create_request(ip=None)

        self.assertEqual(self.backend.authenticate(request, 'test@dimagi.com', '1234'), user)

    def test_can_use_current_key(self):
        user = self._create_user('test@dimagi.com')
        self._create_api_key_for_user(user, key='1234', expiration=datetime(year=2020, month=3, day=10))

        request = self._create_request()

        with freeze_time(datetime(year=2020, month=3, day=9)):
            self.assertEqual(self.backend.authenticate(request, 'test@dimagi.com', '1234'), user)

    def test_cannot_use_expired_key(self):
        user = self._create_user('test@dimagi.com')
        self._create_api_key_for_user(user, key='1234', expiration=datetime(year=2020, month=3, day=10))

        request = self._create_request()

        with freeze_time(datetime(year=2020, month=3, day=11)):
            self.assertIsNone(self.backend.authenticate(request, 'test@dimagi.com', '1234'))

    def setUp(self):
        self.backend = ApiKeyFallbackBackend()

    @classmethod
    def _create_user(cls, username):
        return User.objects.create_user(username=username, password='password')

    @classmethod
    def _create_api_key_for_user(
        cls,
        user,
        name='ApiKey',
        key='1234',
        is_active=True,
        allowed_ips=None,
        domain='',
        expiration=None
    ):
        allowed_ips = allowed_ips or []
        return HQApiKey.objects.create(
            user=user,
            key=key,
            name=name,
            ip_allowlist=allowed_ips,
            domain=domain,
            is_active=is_active,
            expiration_date=expiration
        )

    @classmethod
    def _create_request(cls, can_use_api_key=True, for_domain='test-domain', ip='127.0.0.1'):
        request = HttpRequest()
        request.domain = for_domain

        if ip:
            request.META['HTTP_X_FORWARDED_FOR'] = ip

        if can_use_api_key:
            request.check_for_api_key_as_password = True

        return request


class HQApiKeyAuthenticationTests(TestCase):
    def test_successful_attempt_returns_true(self):
        user = self._create_user('test@dimagi.com')
        self._create_api_key_for_user(user, key='1234')
        request = self._create_request(username='test@dimagi.com', api_key='1234')

        auth = HQApiKeyAuthentication()

        self.assertIs(auth.is_authenticated(request), True)

    def test_bad_api_key_returns_unauthorized(self):
        user = self._create_user('test@dimagi.com')
        self._create_api_key_for_user(user, key='1234')
        request = self._create_request(username='test@dimagi.com', api_key='5678')

        auth = HQApiKeyAuthentication()

        response = auth.is_authenticated(request)

        self.assertEqual(response.status_code, 401)

    def test_cannot_authenticate_with_inactive_key(self):
        user = self._create_user('test@dimagi.com')
        self._create_api_key_for_user(user, key='1234', is_active=False)
        request = self._create_request(username='test@dimagi.com', api_key='1234')

        auth = HQApiKeyAuthentication()

        response = auth.is_authenticated(request)

        self.assertEqual(response.status_code, 401)

    def test_can_authenticate_with_domain_restricted_key(self):
        user = self._create_user('test@dimagi.com')
        self._create_api_key_for_user(user, key='1234', domain='test-domain')
        request = self._create_request(username='test@dimagi.com', api_key='1234', for_domain='test-domain')

        auth = HQApiKeyAuthentication()

        self.assertIs(auth.is_authenticated(request), True)

    def test_does_not_allow_cross_domain_access(self):
        user = self._create_user('test@dimagi.com')
        self._create_api_key_for_user(user, key='1234', domain='test-domain1')
        request = self._create_request(username='test@dimagi.com', api_key='1234', for_domain='test-domain2')

        auth = HQApiKeyAuthentication()

        response = auth.is_authenticated(request)

        self.assertEqual(response.status_code, 401)

    def test_user_can_authenticate_if_ip_is_on_whitelist(self):
        user = self._create_user('test@dimagi.com')
        self._create_api_key_for_user(user, key='1234', allowed_ips=['127.0.0.1'])
        request = self._create_request(username='test@dimagi.com', api_key='1234', ip='127.0.0.1')

        auth = HQApiKeyAuthentication()

        self.assertIs(auth.is_authenticated(request), True)

    def test_user_cannot_authenticate_with_an_ip_not_in_whitelist(self):
        user = self._create_user('test@dimagi.com')
        self._create_api_key_for_user(user, key='1234', allowed_ips=['127.0.0.1'])
        request = self._create_request(username='test@dimagi.com', api_key='1234', ip='5.5.5.5')

        auth = HQApiKeyAuthentication()

        response = auth.is_authenticated(request)

        self.assertEqual(response.status_code, 401)

    def test_allows_empty_ip_for_non_ip_restrictive_keys(self):
        user = self._create_user('test@dimagi.com')
        self._create_api_key_for_user(user, key='1234', allowed_ips=[])

        auth = HQApiKeyAuthentication()

        request = self._create_request(username='test@dimagi.com', api_key='1234', ip=None)

        self.assertIs(auth.is_authenticated(request), True)

    def test_user_can_authenticate_with_current_key(self):
        user = self._create_user('test@dimagi.com')
        self._create_api_key_for_user(user, key='1234', expiration=datetime(year=2020, month=3, day=10))
        request = self._create_request(username='test@dimagi.com', api_key='1234')

        auth = HQApiKeyAuthentication()

        with freeze_time(datetime(year=2020, month=3, day=9)):
            self.assertIs(auth.is_authenticated(request), True)

    def test_user_cannot_authenticate_with_expired_key(self):
        user = self._create_user('test@dimagi.com')
        self._create_api_key_for_user(user, key='1234', expiration=datetime(year=2020, month=3, day=10))
        request = self._create_request(username='test@dimagi.com', api_key='1234')

        auth = HQApiKeyAuthentication()

        with freeze_time(datetime(year=2020, month=3, day=11)):
            response = auth.is_authenticated(request)
            self.assertEqual(response.status_code, 401)

    def test_user_can_authenticate_to_urls_lacking_domain_with_domain_scoped_keys(self):
        user = self._create_user('test@dimagi.com')
        self._create_api_key_for_user(user, key='1234', domain='test-domain')
        request = self._create_request(username='test@dimagi.com', api_key='1234', for_domain='')

        auth = HQApiKeyAuthentication()

        self.assertIs(auth.is_authenticated(request), True)

    @classmethod
    def _create_user(cls, username):
        return User.objects.create_user(username=username, password='password')

    @classmethod
    def _create_api_key_for_user(
            cls,
            user,
            name='ApiKey',
            key='1234',
            is_active=True,
            allowed_ips=None,
            domain='',
            expiration=None
    ):
        allowed_ips = allowed_ips or []
        return HQApiKey.objects.create(
            user=user,
            key=key,
            name=name,
            ip_allowlist=allowed_ips,
            domain=domain,
            is_active=is_active,
            expiration_date=expiration
        )

    @classmethod
    def _create_request(cls, username='test@dimagi.com', api_key='1234', for_domain='test-domain', ip='127.0.0.1'):
        request = HttpRequest()
        request.domain = for_domain
        request.META['HTTP_AUTHORIZATION'] = f'ApiKey {username}:{api_key}'

        if ip:
            request.META['HTTP_X_FORWARDED_FOR'] = ip

        return request

    def test_domain_scoped_api_key_allows_authentication_to_domain_agnostic_urls(self):
        user = self._create_user('test@dimagi.com')
        self._create_api_key_for_user(user, key='1234', domain='test-domain')
        request = self._create_request(username='test@dimagi.com', api_key='1234', for_domain='')

        auth = HQApiKeyAuthentication()

        self.assertIs(auth.is_authenticated(request), True)
