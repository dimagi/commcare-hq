from django.test import TestCase

from corehq import privileges

from corehq.apps.domain.auth import get_active_users_by_email
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.users.models import WebUser, CommCareUser
from corehq.apps.users.util import generate_mobile_username
from corehq.util.test_utils import privilege_enabled


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

    @privilege_enabled(privileges.TWO_STAGE_MOBILE_WORKER_ACCOUNT_CREATION)
    def test_mobile_worker_included_with_flag(self):
        email = 'mw-included@example.com'
        mobile_worker = CommCareUser.create(self.domain, 'mw-included', 's3cr3t', None, None, email=email)
        self.addCleanup(mobile_worker.delete, self.domain, deleted_by=None)
        results = list(get_active_users_by_email(email))
        self.assertEqual(1, len(results))
        self.assertEqual(mobile_worker.username, results[0].username)

    def test_mobile_worker_lookup(self):
        chosen_username = 'active-user'
        email = 'mw-included@example.com'
        mobile_system_username = generate_mobile_username(chosen_username, self.domain, False)
        active_user = CommCareUser.create(self.domain, mobile_system_username, 's3cr3t', None, None, email=email)
        self.addCleanup(active_user.delete, self.domain, deleted_by=None)
        results = list(get_active_users_by_email(mobile_system_username))
        self.assertEqual(1, len(results))
        self.assertEqual(active_user.username, results[0].username)

    @privilege_enabled(privileges.TWO_STAGE_MOBILE_WORKER_ACCOUNT_CREATION)
    def test_domain_limited_mobile_worker_lookup(self):
        other_domain = 'other-domain'
        email = 'active-user@example.com'

        web_user = WebUser.create(self.domain, email, 's3cr3t', None, None)
        included_mobile_worker = CommCareUser.create(self.domain, 'included-user',
                                                     's3cr3t', None, None, email=email)
        excluded_user = CommCareUser.create(other_domain, 'excluded-user', 's3cr3t', None, None, email=email)

        self.addCleanup(excluded_user.delete, other_domain, deleted_by=None)
        self.addCleanup(included_mobile_worker.delete, self.domain, deleted_by=None)
        self.addCleanup(web_user.delete, self.domain, deleted_by=None)

        results = list(get_active_users_by_email(email, self.domain))
        self.assertEqual(2, len(results))
        results_usernames = [user.username for user in results]
        self.assertIn(included_mobile_worker.username, results_usernames)
        self.assertIn(web_user.username, results_usernames)
