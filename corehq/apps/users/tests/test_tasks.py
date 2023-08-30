import uuid
from contextlib import contextmanager
from datetime import datetime, timedelta

from django.test import TestCase

from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.enterprise.tests.utils import create_enterprise_permissions
from corehq.apps.users.dbaccessors import delete_all_users
from corehq.apps.users.models import CommCareUser, WebUser
from corehq.apps.users.tasks import (
    apply_correct_demo_mode_to_loadtest_user,
    update_domain_date,
)
from corehq.apps.es.tests.utils import es_test
from corehq.apps.es import case_search_adapter
from corehq.form_processor.models import CommCareCase
from corehq.apps.users.tasks import remove_users_test_cases
from corehq.apps.reports.util import domain_copied_cases_by_owner
from corehq.apps.hqcase.case_helper import CaseCopier


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


@es_test(requires=[case_search_adapter])
class TestRemoveUsersTestCases(TestCase):

    domain = "test-domain"

    @classmethod
    def setUpClass(cls):
        super()
        cls.user = CommCareUser.create(cls.domain, 'user', 'password', None, None)

    @classmethod
    def tearDownClass(cls):
        cls.user.delete(deleted_by_domain=None, deleted_by=None)
        super()

    def test_only_copied_cases_gets_removed(self):
        _ = self._send_case_to_es(owner_id=self.user.user_id)
        test_case = self._send_case_to_es(owner_id=self.user.user_id, is_copy=True)

        remove_users_test_cases(self.domain, [self.user.user_id])
        case_ids = domain_copied_cases_by_owner(self.domain, self.user.user_id)

        self.assertEqual(case_ids, [test_case.case_id])

    def _send_case_to_es(
        self,
        owner_id=None,
        is_copy=False,
    ):
        case_json = {}
        if is_copy:
            case_json[CaseCopier.COMMCARE_CASE_COPY_PROPERTY_NAME] = 'case_id'

        case = CommCareCase(
            case_id=uuid.uuid4().hex,
            domain=self.domain,
            owner_id=owner_id,
            type='case_type',
            case_json=case_json,
            modified_on=datetime.utcnow(),
            server_modified_on=datetime.utcnow(),
        )
        case.save()

        case_search_adapter.index(case, refresh=True)
        return case
