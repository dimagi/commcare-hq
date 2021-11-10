from datetime import datetime, timedelta

from django.test import TestCase

from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.enterprise.tests.utils import create_enterprise_permissions
from corehq.apps.users.dbaccessors import delete_all_users
from corehq.apps.users.models import WebUser
from corehq.apps.users.tasks import update_domain_date


class TasksTest(TestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        delete_all_users()

        # Set up domains
        cls.domain = create_domain('test')
        cls.mirror_domain = create_domain('mirror')
        create_enterprise_permissions('web@web.com', 'test', ['mirror'])

        # Set up user
        cls.web_user = WebUser.create(
            domain='test',
            username='web',
            password='secret',
            created_by=None,
            created_via=None,
        )

        cls.today = datetime.today().date()
        cls.last_week = cls.today - timedelta(days=7)

    @classmethod
    def tearDownClass(cls):
        delete_all_users()
        cls.domain.delete()
        cls.mirror_domain.delete()
        super().tearDownClass()

    def _last_accessed(self, user, domain):
        domain_membership = user.get_domain_membership(domain, allow_enterprise=False)
        if domain_membership:
            return domain_membership.last_accessed
        return None

    def test_update_domain_date_web_user(self):
        self.assertIsNone(self._last_accessed(self.web_user, self.domain.name))
        update_domain_date(self.web_user.user_id, self.domain.name)
        self.web_user = WebUser.get_by_username(self.web_user.username)
        self.assertEqual(self._last_accessed(self.web_user, self.domain.name), self.today)

    def test_update_domain_date_web_user_mirror(self):
        # Mirror domain access shouldn't be updated because user doesn't have a real membership
        self.assertIsNone(self._last_accessed(self.web_user, self.mirror_domain.name))
        update_domain_date(self.web_user.user_id, self.mirror_domain.name)
        self.web_user = WebUser.get_by_username(self.web_user.username)
        self.assertIsNone(self._last_accessed(self.web_user, self.mirror_domain.name))
