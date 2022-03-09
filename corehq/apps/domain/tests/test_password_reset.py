from django.test import TestCase

from corehq.apps.domain.auth import get_active_users_by_email
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.users.models import WebUser, CommCareUser
from corehq.util.test_utils import flag_enabled


class PasswordResetTest(TestCase):
    domain = 'password-reset-test'

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.project = create_domain(cls.domain)

    @classmethod
    def tearDownClass(cls):
        cls.project.delete()
        super().tearDownClass()

    def test_missing(self):
        self.assertEqual(0, len(list(get_active_users_by_email('missing@example.com'))))

    def test_web_user_lookup(self):
        email = 'web-user@example.com'
        web_user = WebUser.create(self.domain, email, 's3cr3t', None, None)
        self.addCleanup(web_user.delete, self.domain, deleted_by=None)
        results = list(get_active_users_by_email(email))
        self.assertEqual(1, len(results))
        self.assertEqual(web_user.username, results[0].username)

    def test_web_user_by_email(self):
        email = 'web-user-email@example.com'
        web_user = WebUser.create(self.domain, 'web-user2@example.com', 's3cr3t', None, None, email=email)
        self.addCleanup(web_user.delete, self.domain, deleted_by=None)
        self.assertEqual(0, len(list(get_active_users_by_email(email))))

    def test_mobile_worker_excluded(self):
        email = 'mw-excluded@example.com'
        mobile_worker = CommCareUser.create(self.domain, 'mw-excluded', 's3cr3t', None, None, email=email)
        self.addCleanup(mobile_worker.delete, self.domain, deleted_by=None)
        results = list(get_active_users_by_email(email))
        self.assertEqual(0, len(results))

    @flag_enabled('TWO_STAGE_USER_PROVISIONING')
    def test_mobile_worker_included_with_flag(self):
        email = 'mw-included@example.com'
        mobile_worker = CommCareUser.create(self.domain, 'mw-included', 's3cr3t', None, None, email=email)
        self.addCleanup(mobile_worker.delete, self.domain, deleted_by=None)
        results = list(get_active_users_by_email(email))
        self.assertEqual(1, len(results))
        self.assertEqual(mobile_worker.username, results[0].username)
