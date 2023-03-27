import uuid
from contextlib import contextmanager
from datetime import datetime, timedelta

from django.test import TestCase

from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.enterprise.tests.utils import create_enterprise_permissions
from corehq.apps.users.dbaccessors import delete_all_users
from corehq.apps.users.models import CommCareUser, WebUser, UserHistory
from corehq.apps.users.tasks import (
    apply_correct_demo_mode_to_loadtest_user,
    update_domain_date,
    clean_domain_users_data,
)
from corehq.apps.hqcase.utils import submit_case_blocks
from casexml.apps.case.mock import CaseBlock


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


class TestLoadtestUserIsDemoUser(TestCase):

    def test_set_loadtest_factor_on_demo_user(self):
        with _get_user(loadtest_factor=5, is_demo_user=True) as user:
            apply_correct_demo_mode_to_loadtest_user(user.user_id)

            user = CommCareUser.get_by_user_id(user.user_id)
            self.assertTrue(user.is_demo_user)
            self.assertFalse(user.is_loadtest_user)

    def test_set_loadtest_factor_on_non_demo_user(self):
        with _get_user(loadtest_factor=5, is_demo_user=False) as user:
            apply_correct_demo_mode_to_loadtest_user(user.user_id)

            user = CommCareUser.get_by_user_id(user.user_id)
            self.assertTrue(user.is_demo_user)
            self.assertTrue(user.is_loadtest_user)

    def test_unset_loadtest_factor_on_demo_user(self):
        with _get_user(loadtest_factor=None, is_demo_user=True) as user:
            self.assertFalse(user.is_loadtest_user)
            apply_correct_demo_mode_to_loadtest_user(user.user_id)

            user = CommCareUser.get_by_user_id(user.user_id)
            self.assertTrue(user.is_demo_user)
            self.assertFalse(user.is_loadtest_user)

    def test_unset_loadtest_factor_on_non_demo_user(self):
        with _get_user(loadtest_factor=None, is_demo_user=False) as user:
            user.is_loadtest_user = True
            apply_correct_demo_mode_to_loadtest_user(user.user_id)

            user = CommCareUser.get_by_user_id(user.user_id)
            self.assertFalse(user.is_demo_user)
            self.assertFalse(user.is_loadtest_user)


@contextmanager
def _get_user(loadtest_factor, is_demo_user):
    domain_name = 'test-domain'
    domain_obj = create_domain(domain_name)
    just_now = datetime.utcnow().isoformat(timespec='seconds') + 'Z'
    user = CommCareUser.wrap({
        'domain': domain_name,
        'username': f'testy@{domain_name}.commcarehq.org',
        'loadtest_factor': loadtest_factor,
        'is_demo_user': is_demo_user,
        'user_data': {},
        'date_joined': just_now,
    })
    user.save()
    try:
        yield user

    finally:
        user.delete(domain_name, None)
        domain_obj.delete()


class TestCleanDomainUserData(TestCase):

    USERNAME_1 = 'user_1'
    USERNAME_2 = 'user_2'
    DOMAIN = 'test-domain'

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.domain_obj = create_domain(cls.DOMAIN)
        cls.webuser = WebUser.create(cls.DOMAIN, 'test', '****', None, None)
        cls.webuser.save()

        cls.user_1 = CommCareUser.create(
            cls.DOMAIN, cls.USERNAME_1, "****", None, None)
        cls.user_2 = CommCareUser.create(
            cls.DOMAIN, cls.USERNAME_2, "****", None, None)

    @classmethod
    def tearDownClass(cls):
        cls.domain_obj.delete()
        super().tearDownClass()

    def test_users_data_is_cleared(self):
        self._populate_user_data(self.user_1)
        self._populate_user_data(self.user_2)

        self.assertTrue(len(self.user_1._get_form_ids()) == 1)
        self.assertTrue(len(self.user_1._get_case_ids()) == 1)

        clean_domain_users_data(
            domain=self.domain_obj.name,
            user_ids=[self.user_1.user_id, self.user_2.user_id],
            cleared_by=self.webuser,
        )

        self.assertTrue(len(self.user_1._get_form_ids()) == 0)
        self.assertTrue(len(self.user_1._get_case_ids()) == 0)
        self.assertTrue(len(self.user_2._get_form_ids()) == 0)
        self.assertTrue(len(self.user_2._get_case_ids()) == 0)

        user_1_history = UserHistory.objects.filter(
            by_domain=self.DOMAIN,
            user_id=self.user_1.user_id,
        )
        self.assertTrue(len(user_1_history) == 1)
        self.assertTrue(user_1_history[0].action == UserHistory.CLEAR)

    def _populate_user_data(self, user):
        self._create_case(user.user_id)
        self._create_form(user.user_id)

    def _create_case(self, user_id):
        submit_case_blocks(
            [
                CaseBlock(
                    create=True,
                    case_id=uuid.uuid4().hex,
                    user_id=user_id
                ).as_text()
            ], domain=self.DOMAIN
        )

    def _create_form(self, user_id):
        from corehq.apps.receiverwrapper.util import submit_form_locally

        form = """
        <data xmlns="http://openrosa.org/formdesigner/blah">
            <meta>
                <userID>{user_id}</userID>
                <deviceID>{device_id}</deviceID>
            </meta>
        </data>
        """
        submit_form_locally(
            form.format(user_id=user_id, device_id=uuid.uuid4()),
            self.DOMAIN,
        )
