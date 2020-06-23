from datetime import datetime

from django.conf import settings
from django.test import Client, TestCase
from django.urls import reverse

from corehq.apps.domain.models import Domain
from corehq.apps.domain.views.settings import DefaultProjectSettingsView
from corehq.apps.users.models import WebUser
from corehq.util.test_utils import flag_enabled


@flag_enabled('SECURE_SESSION_TIMEOUT')
class TestTimeout(TestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.insecure_domain = Domain(name="cosmos", is_active=True)
        cls.insecure_domain.save()

        cls.username = 'elle'
        cls.password = '*******'
        cls.user = WebUser.create(cls.insecure_domain.name, cls.username, cls.password, None, None, is_admin=True)

        cls.secure_domain1 = Domain(name="fortress-1", is_active=True)
        cls.secure_domain1.secure_sessions = True
        cls.secure_domain1.save()

        cls.secure_domain2 = Domain(name="fortress-2", is_active=True)
        cls.secure_domain2.secure_sessions = True
        cls.secure_domain2.secure_sessions_timeout = 15
        cls.secure_domain2.save()

    def setUp(self):
        # Re-login for each test to create new session
        self.client = Client()
        self.client.login(username=self.username, password=self.password)

    def tearDown(self):
        self.user = WebUser.get_by_username(self.user.username)
        domains = set(self.user.domains)
        domains.remove(self.insecure_domain.name)
        if domains:
            for domain in domains:
                self.user.delete_domain_membership(domain)
            self.user.save()

    @classmethod
    def tearDownClass(cls):
        cls.user.delete()
        cls.insecure_domain.delete()
        cls.secure_domain1.delete()
        cls.secure_domain2.delete()
        super().tearDownClass()

    def _assert_session_expiry_in_minutes(self, expected_minutes, session):
        self.assertEqual(expected_minutes, session.get('secure_session_timeout'))
        delta = session.get_expiry_date() - datetime.utcnow()
        diff_in_minutes = delta.days * 24 * 60 + delta.seconds / 60
        self.assertEqual(expected_minutes, round(diff_in_minutes))

    def _get_page(self, domain=None):
        if domain:
            self.client.get(reverse(DefaultProjectSettingsView.urlname, args=[domain.name]))
        else:
            self.client.get(reverse('my_account_settings'))

    def test_insecure(self):
        self._get_page(self.insecure_domain)
        self.assertFalse(self.client.session.get('secure_session'))
        self._assert_session_expiry_in_minutes(settings.INACTIVITY_TIMEOUT, self.client.session)

    def test_secure(self):
        # visit a secure domain
        self._get_page(self.secure_domain1)
        self.assertTrue(self.client.session.get('secure_session'))
        self._assert_session_expiry_in_minutes(settings.SECURE_TIMEOUT, self.client.session)

        # settings should be retained when going to a non-domain page
        self._get_page()
        self.assertTrue(self.client.session.get('secure_session'))
        self._assert_session_expiry_in_minutes(settings.SECURE_TIMEOUT, self.client.session)

    def test_secure_membership(self):
        # If a user is a member of a secure domain, all of their sessions are secure
        self.user = WebUser.get_by_username(self.user.username)
        self.user.add_as_web_user(self.secure_domain1.name, 'admin')

        self._get_page(self.insecure_domain)
        self.assertTrue(self.client.session.get('secure_session'))
        self._assert_session_expiry_in_minutes(settings.SECURE_TIMEOUT, self.client.session)

    def test_configurable_timeout(self):
        self._get_page(self.secure_domain2)
        self.assertTrue(self.client.session.get('secure_session'))
        self._assert_session_expiry_in_minutes(self.secure_domain2.secure_sessions_timeout, self.client.session)

    def test_multiple_secure(self):
        # Session should apply minimum value of all relevant timeouts
        self.user = WebUser.get_by_username(self.user.username)
        self.user.add_as_web_user(self.secure_domain1.name, 'admin')
        self.user.add_as_web_user(self.secure_domain2.name, 'admin')
        self._get_page()
        self.assertTrue(self.client.session.get('secure_session'))
        self._assert_session_expiry_in_minutes(self.secure_domain2.secure_sessions_timeout, self.client.session)
