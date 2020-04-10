from django.test import TestCase

from corehq.apps.domain.auth import get_active_users_by_email
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.users.models import WebUser, CommCareUser


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
        self.assertEqual(0, get_active_users_by_email('missing@example.com').count())

    def test_web_user_lookup(self):
        email = 'web-user@example.com'
        web_user = WebUser.create(self.domain, email, 's3cr3t')
        self.addCleanup(web_user.delete)
        results = get_active_users_by_email(email)
        self.assertEqual(1, results.count())
        self.assertEqual(web_user.username, results[0].username)

    def test_mobile_worker_excluded(self):
        email = 'mw-excluded@example.com'
        mobile_worker = CommCareUser.create(self.domain, 'mw-excluded', 's3cr3t', email=email)
        self.addCleanup(mobile_worker.delete)
        results = get_active_users_by_email(email)
        self.assertEqual(0, results.count())
