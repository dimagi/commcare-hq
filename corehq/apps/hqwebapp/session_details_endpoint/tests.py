import datetime
import json
from unittest.mock import patch
from uuid import uuid4

import pytz

from django.conf import settings
from django.contrib.auth.models import User
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from django.utils.dateparse import parse_datetime

from corehq import toggles
from corehq.apps.domain.models import Domain
from corehq.apps.public_webforms.models import PublicFormSession, PublicWebform
from corehq.apps.sso.models import (
    AuthenticatedEmailDomain,
    IdentityProvider,
    TrustedIdentityProvider,
)
from corehq.apps.sso.tests import generator as sso_generator
from corehq.apps.users.models import CommCareUser, WebUser
from corehq.util.hmac_request import get_hmac_digest
from corehq.util.test_utils import flag_enabled, softer_assert


class SessionDetailsViewTest(TestCase):
    @classmethod
    def setUpClass(cls):
        super(SessionDetailsViewTest, cls).setUpClass()
        cls.domain = Domain.get_or_create_with_name('toyland', is_active=True)
        cls.addClassCleanup(cls.domain.delete)
        cls.couch_user = CommCareUser.create(cls.domain.name, 'bunkey', '123', None, None)
        cls.addClassCleanup(cls.couch_user.delete, cls.domain.name, deleted_by=None)
        cls.sql_user = cls.couch_user.get_django_user()

        cls.expected_response = {
            'username': cls.sql_user.username,
            'djangoUserId': cls.sql_user.pk,
            'superUser': cls.sql_user.is_superuser,
            'authToken': None,
            'domains': [cls.domain.name],
            'public': False,
            'enabled_toggles': [],
            'enabled_previews': [],
        }
        cls.url = reverse('session_details')

    def setUp(self):
        # logs in the mobile worker every test so a new session is setup
        self.client = Client()
        self.client.login(username='bunkey', password='123')

        self.session = self.client.session
        self.session.save()
        self.session_key = self.session.session_key
        self.expected_response['authToken'] = self.session_key

    def _assert_session_expiry_in_minutes(self, expected_minutes, actual_time_string):
        delta = parse_datetime(actual_time_string) - datetime.datetime.utcnow().replace(tzinfo=pytz.utc)
        diff_in_minutes = delta.days * 24 * 60 + delta.seconds / 60
        self.assertEqual(expected_minutes, round(diff_in_minutes))

    @softer_assert()
    def test_session_details_view(self):
        data = json.dumps({'sessionId': self.session_key, 'domain': self.domain.name})
        response = _post_with_hmac(self.url, data, content_type="application/json")
        self.assertEqual(200, response.status_code)
        self.assertJSONEqual(response.content, self.expected_response)

    @softer_assert()
    def test_session_details_view_expired_session(self):
        self.session.set_expiry(-1)  # 1 second in the past
        self.session.save()
        data = json.dumps({'sessionId': self.session_key, 'domain': self.domain.name})
        response = _post_with_hmac(self.url, data, content_type="application/json")
        self.assertEqual(404, response.status_code)

    @softer_assert()
    def test_session_details_view_updates_session(self):
        expired_date = self.session.get_expiry_date()
        data = json.dumps({'sessionId': self.session_key, 'domain': self.domain.name})
        response = _post_with_hmac(self.url, data, content_type="application/json")
        self.assertEqual(200, response.status_code)
        self.assertGreater(self.session.get_expiry_date(), expired_date)

    @flag_enabled('SECURE_SESSION_TIMEOUT')
    def test_secure_sessions(self):

        def _assertSecureSessionExpiry(previous_expiry, timeout_in_minutes):
            self.assertEqual(True, self.client.session.get('secure_session'))
            self.assertEqual(timeout_in_minutes, self.client.session.get('secure_session_timeout'))
            self.assertNotEqual(previous_expiry, self.client.session.get_expiry_date())
            expiring_in = (self.client.session.get_expiry_date() - datetime.datetime.utcnow()).seconds
            self.assertGreater(expiring_in, timeout_in_minutes * 60 - 2)
            self.assertLess(expiring_in, timeout_in_minutes * 60 + 2)

        # Turn on secure sessions
        self.domain.secure_sessions = True
        self.domain.save()

        # Sessions should now be secure and use timeout from settings
        expired_date = self.session.get_expiry_date()
        self.client.get(reverse('domain_homepage', args=[self.domain.name]))
        _assertSecureSessionExpiry(expired_date, settings.SECURE_TIMEOUT)

        # Turn on customized timeout
        custom_timeout = 10
        self.domain.secure_sessions_timeout = custom_timeout
        self.domain.save()

        # Request a domain-specific page so the domain-specific timeout kicks in
        expired_date = self.session.get_expiry_date()
        self.client.get(reverse('domain_homepage', args=[self.domain.name]))
        _assertSecureSessionExpiry(expired_date, custom_timeout)

        # Request a non-domain-specific page, which still uses the domain-specific timeout saved in the session
        expired_date = self.session.get_expiry_date()
        self.client.get(reverse('ping_session'))
        _assertSecureSessionExpiry(expired_date, custom_timeout)

        # Test the session details view itself
        expired_date = self.session.get_expiry_date()
        data = json.dumps({'sessionId': self.session_key, 'domain': self.domain.name})
        response = _post_with_hmac(self.url, data, content_type="application/json")
        self.assertEqual(200, response.status_code)
        _assertSecureSessionExpiry(expired_date, custom_timeout)

        # Going back to insecure sessions requires a logout to create a new session
        self.domain.secure_sessions_timeout = None
        self.domain.secure_sessions = False
        self.domain.save()
        self.client.logout()
        self.client.login(username='bunkey', password='123')
        self.client.get(reverse('domain_homepage', args=[self.domain.name]))
        self.assertEqual(False, self.client.session.get('secure_session'))
        self.assertEqual(settings.INACTIVITY_TIMEOUT, self.client.session.get('secure_session_timeout'))

    def test_ping_login_unauth_user(self):
        client = Client()
        client.login(username='jackalope', password='456')
        response = client.get(reverse('ping_login'))
        self.assertEqual(200, response.status_code)
        data = json.loads(response.content)
        self.assertFalse(data['success'])
        self.assertIsNone(data['session_expiry'])
        self.assertIsNone(data['secure_session_timeout'])
        self.assertFalse(data['secure_session'])
        self.assertEqual("", data['username'])

    def test_ping_login_auth_user(self):
        client = Client()
        client.login(username=self.couch_user.username, password='123')

        # First ping after login via client.login: authorized but no session expiry
        response = client.get(reverse('ping_login'))
        self.assertEqual(200, response.status_code)
        data = json.loads(response.content)
        self.assertTrue(data['success'])
        self.assertIsNone(data['session_expiry'])
        self.assertIsNone(data['secure_session_timeout'])
        self.assertFalse(data['secure_session'])
        self.assertEqual(self.couch_user.username, data['username'])

        # Request a page and then re-ping: session expiry should be based on INACTIVITY_TIMEOUT
        client.get(reverse('bsd_license'))
        response = client.get(reverse('ping_login'))
        data = json.loads(response.content)
        self.assertTrue(data['success'])
        self.assertEqual(self.couch_user.username, data['username'])
        self.assertFalse(data['secure_session'])
        self.assertEqual(settings.INACTIVITY_TIMEOUT, data['secure_session_timeout'])
        self._assert_session_expiry_in_minutes(settings.INACTIVITY_TIMEOUT, data['session_expiry'])

        # Ping some more, session_expiry should not change
        session_expiry = data['session_expiry']
        client.get(reverse('ping_login'))
        response = client.get(reverse('ping_login'))
        data = json.loads(response.content)
        self.assertTrue(data['success'])
        self.assertEqual(self.couch_user.username, data['username'])
        self.assertEqual(session_expiry, data['session_expiry'])

        # Request a normal page, session_expiry should update
        client.get(reverse('bsd_license'))
        response = client.get(reverse('ping_login'))
        data = json.loads(response.content)
        self.assertTrue(data['success'])
        self.assertEqual(self.couch_user.username, data['username'])
        self.assertIsNotNone(data['session_expiry'])
        self.assertNotEqual(session_expiry, data['session_expiry'])

    def test_with_hmac_signing(self):
        data = json.dumps({'sessionId': self.session_key, 'domain': self.domain.name})
        header_value = get_hmac_digest(settings.FORMPLAYER_INTERNAL_AUTH_KEY, data)
        response = Client().post(
            self.url,
            data,
            content_type="application/json",
            HTTP_X_MAC_DIGEST=header_value
        )
        self.assertEqual(200, response.status_code)
        self.assertJSONEqual(response.content, self.expected_response)

    def test_with_hmac_signing_fail(self):
        data = json.dumps({'sessionId': self.session_key, 'domain': self.domain.name})

        response = Client().post(
            self.url,
            data,
            content_type="application/json",
            HTTP_X_MAC_DIGEST='bad signature'
        )
        self.assertEqual(401, response.status_code)

    @softer_assert()
    @flag_enabled('SECURE_SESSION_TIMEOUT')
    @flag_enabled('CALC_XPATHS', is_preview=True)
    def test_session_details_view_toggles(self):
        toggles.all_toggles()
        data = json.dumps({'sessionId': self.session_key, 'domain': self.domain.name})
        response = _post_with_hmac(self.url, data, content_type="application/json")
        self.assertEqual(200, response.status_code)
        expected_response = self.expected_response.copy()
        expected_response['enabled_toggles'] = ['SECURE_SESSION_TIMEOUT']
        expected_response['enabled_previews'] = ['CALC_XPATHS']
        self.assertJSONEqual(response.content, expected_response)


class PublicSessionDetailsViewTest(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.domain = Domain.get_or_create_with_name('publictoyland', is_active=True)
        cls.addClassCleanup(cls.domain.delete)
        cls.url = reverse('session_details')

    def _make_session(self, expires_at=None, submitted_at=None):
        future_expiration = datetime.datetime.today() + datetime.timedelta(days=30)
        webform = PublicWebform.objects.create(
            domain=self.domain.name,
            app_id='app',
            app_build_id='build',
            form_unique_id='form',
            endpoint_id='endpoint',
            session_type='survey',
            allow_sms=False,
            allow_email=True,
            expires_at=future_expiration,
        )
        return PublicFormSession.objects.create(
            public_webform=webform,
            expires_at=expires_at or future_expiration,
            submitted_at=submitted_at,
        )

    def test_valid_public_session(self):
        session = self._make_session()
        data = json.dumps({'publicSessionKey': str(session.session_key)})
        response = _post_with_hmac(self.url, data, content_type="application/json")
        assert response.status_code == 200
        assert json.loads(response.content) == {
            'username': session.session_username,
            'djangoUserId': None,
            'superUser': False,
            'authToken': str(session.session_key),
            'domains': [self.domain.name],
            'public': True,
            'enabled_toggles': [],
            'enabled_previews': [],
        }

    def test_unknown_public_session_key(self):
        data = json.dumps({'publicSessionKey': str(uuid4())})
        response = _post_with_hmac(self.url, data, content_type="application/json")
        assert response.status_code == 404

    def test_invalid_public_session_key(self):
        data = json.dumps({'publicSessionKey': 'not-a-uuid'})
        response = _post_with_hmac(self.url, data, content_type="application/json")
        assert response.status_code == 404

    def test_expired_public_session(self):
        session = self._make_session(expires_at=datetime.datetime(2000, 1, 1))
        data = json.dumps({'publicSessionKey': str(session.session_key)})
        response = _post_with_hmac(self.url, data, content_type="application/json")
        assert response.status_code == 404

    def test_submitted_public_session(self):
        session = self._make_session(submitted_at=datetime.datetime(2020, 1, 1))
        data = json.dumps({'publicSessionKey': str(session.session_key)})
        response = _post_with_hmac(self.url, data, content_type="application/json")
        assert response.status_code == 404


class SessionDetailsAccessChecksTest(TestCase):
    """One test per answer the endpoint gives about a project space."""

    def _login(self, domain_name, **domain_attrs):
        domain = Domain.get_or_create_with_name(domain_name, is_active=True)
        self.addCleanup(lambda: Domain.get_by_name(domain_name).delete())
        WebUser.create(domain_name, f'u-{domain_name}', 'shhh', None, None)
        self.addCleanup(
            lambda: WebUser.get_by_username(f'u-{domain_name}').delete(domain_name, deleted_by=None)
        )
        if domain_attrs:
            for name, value in domain_attrs.items():
                setattr(domain, name, value)
            domain.save()
        client = Client()
        assert client.login(username=f'u-{domain_name}', password='shhh')
        return client.session.session_key

    def _post(self, session_key, domain_name):
        data = json.dumps({'sessionId': session_key, 'domain': domain_name})
        return _post_with_hmac(reverse('session_details'), data, content_type="application/json")

    def test_member_is_allowed(self):
        session_key = self._login('checks-member')
        assert self._post(session_key, 'checks-member').status_code == 200

    def test_deactivated_user_is_refused(self):
        session_key = self._login('checks-deact')
        user = User.objects.get(username='u-checks-deact')
        user.is_active = False
        user.save()
        assert self._post(session_key, 'checks-deact').status_code == 404

    def test_changed_password_is_refused(self):
        session_key = self._login('checks-pw')
        user = User.objects.get(username='u-checks-pw')
        user.set_password('a-new-password')
        user.save()
        assert self._post(session_key, 'checks-pw').status_code == 404

    def test_deactivated_in_project_space_is_refused(self):
        session_key = self._login('checks-indom')
        web_user = WebUser.get_by_username('u-checks-indom')
        web_user.set_is_active('checks-indom', False)
        web_user.save()
        assert self._post(session_key, 'checks-indom').status_code == 404

    def test_inactive_project_space_is_refused(self):
        session_key = self._login('checks-inactive', is_active=False)
        assert self._post(session_key, 'checks-inactive').status_code == 404

    def test_unsatisfied_two_factor_is_refused(self):
        session_key = self._login('checks-2fa', two_factor_auth=True)
        assert self._post(session_key, 'checks-2fa').status_code == 404

    def test_project_space_they_do_not_belong_to_is_refused(self):
        session_key = self._login('checks-member2')
        other = Domain.get_or_create_with_name('checks-other', is_active=True)
        self.addCleanup(other.delete)
        assert self._post(session_key, 'checks-other').status_code == 404

    def test_unrecognised_project_space_is_refused(self):
        session_key = self._login('checks-unknown')
        assert self._post(session_key, 'no-such-project-space').status_code == 404

    def test_deactivated_mobile_worker_is_refused(self):
        domain = Domain.get_or_create_with_name('checks-mobile', is_active=True)
        self.addCleanup(lambda: Domain.get_by_name('checks-mobile').delete())
        CommCareUser.create('checks-mobile', 'mw', 'shhh', None, None)
        self.addCleanup(
            lambda: CommCareUser.get_by_username('mw').delete('checks-mobile', deleted_by=None)
        )
        client = Client()
        assert client.login(username='mw', password='shhh')
        session_key = client.session.session_key

        worker = CommCareUser.get_by_username('mw')
        worker.is_active = False
        worker.save()

        assert self._post(session_key, domain.name).status_code == 404

    def test_superuser_is_refused_a_project_space_that_restricts_them(self):
        session_key = self._login('checks-super')
        superuser = WebUser.get_by_username('u-checks-super')
        superuser.is_superuser = True
        superuser.save()
        restricted = Domain.get_or_create_with_name('checks-restricted', is_active=True)
        restricted.restrict_superusers = True
        restricted.save()
        self.addCleanup(lambda: Domain.get_by_name('checks-restricted').delete())

        assert self._post(session_key, 'checks-restricted').status_code == 404

    @override_settings(IS_SAAS_ENVIRONMENT=True)
    def test_lapsed_project_access_is_refused(self):
        session_key = self._login('checks-privilege')
        with patch('corehq.apps.domain.decorators.has_privilege', return_value=False):
            assert self._post(session_key, 'checks-privilege').status_code == 404


class SessionDetailsSsoChecksTest(TestCase):
    """An SSO user is served only where the project space trusts their provider."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.account = sso_generator.get_billing_account_for_idp()
        cls.domain = Domain.get_or_create_with_name('sso-checks', is_active=True)
        cls.addClassCleanup(cls.domain.delete)
        cls.user = WebUser.create(cls.domain.name, 'jorge@helpingearth.org', 'shhh', None, None)
        cls.addClassCleanup(cls.user.delete, cls.domain.name, deleted_by=None)
        cls.idp = sso_generator.create_idp('helping-earth', cls.account)
        cls.idp.is_active = True
        cls.idp.save()
        AuthenticatedEmailDomain.objects.create(
            email_domain='helpingearth.org', identity_provider=cls.idp,
        )
        cls.addClassCleanup(IdentityProvider.objects.all().delete)
        cls.addClassCleanup(AuthenticatedEmailDomain.objects.all().delete)

    def tearDown(self):
        TrustedIdentityProvider.objects.all().delete()
        super().tearDown()

    def _sso_session_key(self):
        client = Client()
        assert client.login(username='jorge@helpingearth.org', password='shhh')
        session = client.session
        session['samlSessionIndex'] = '_7c84c96e-8774-4e64-893c-06f91d285100'
        session.save()
        return session.session_key

    def _post(self, session_key):
        data = json.dumps({'sessionId': session_key, 'domain': self.domain.name})
        return _post_with_hmac(reverse('session_details'), data, content_type="application/json")

    def test_untrusted_identity_provider_is_refused(self):
        assert self._post(self._sso_session_key()).status_code == 404

    def test_trusted_identity_provider_is_allowed(self):
        self.idp.create_trust_with_domain(self.domain.name, self.user.username)
        assert self._post(self._sso_session_key()).status_code == 200


def _post_with_hmac(url, data, client=None, **kwargs):
    header_value = get_hmac_digest(settings.FORMPLAYER_INTERNAL_AUTH_KEY, data)
    client = client or Client()
    return client.post(url, data, HTTP_X_MAC_DIGEST=header_value, **kwargs)
