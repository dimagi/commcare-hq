from django.test import TestCase

from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.es.tests.utils import es_test
from corehq.apps.es.users import (
    UserES,
    _empty_user_data_property,
    _missing_user_data_property,
    missing_or_empty_user_data_property,
    user_adapter,
)
from corehq.apps.users.models import CommCareUser, WebUser


@es_test(requires=[user_adapter], setup_class=True)
class TestUserDataFilters(TestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.domain = 'user-data-es-test'
        cls.domain_obj = create_domain(cls.domain)
        cls.addClassCleanup(cls.domain_obj.delete)

        cls.user_with_data = CommCareUser.create(
            username="user1",
            domain=cls.domain,
            password="***********",
            created_by=None,
            created_via=None,
            user_data={'location': 'Boston'}
        )
        cls.user_empty_data = CommCareUser.create(
            username="user2",
            domain=cls.domain,
            password="***********",
            created_by=None,
            created_via=None,
            user_data={'location': ''}
        )
        cls.user_no_data = CommCareUser.create(
            username="user3",
            domain=cls.domain,
            password="***********",
            created_by=None,
            created_via=None
        )
        cls.user_other_data = CommCareUser.create(
            username="user4",
            domain=cls.domain,
            password="***********",
            created_by=None,
            created_via=None,
            user_data={'other_prop': 'value'}
        )

        for user in [cls.user_with_data, cls.user_empty_data, cls.user_no_data, cls.user_other_data]:
            user_adapter.index(user, refresh=True)
            cls.addClassCleanup(user.delete, None, None)

    def test_missing_or_empty_user_data_property(self):
        results = (UserES()
                   .domain(self.domain)
                   .filter(missing_or_empty_user_data_property('location'))
                   .get_ids())

        expected_ids = [self.user_no_data.user_id, self.user_empty_data.user_id, self.user_other_data.user_id]
        self.assertCountEqual(results, expected_ids)

    def test_missing_or_empty_user_data_multiple_properties(self):
        results = (UserES()
                   .domain(self.domain)
                   .filter(missing_or_empty_user_data_property('location'))
                   .filter(missing_or_empty_user_data_property('other_prop'))
                   .get_ids())

        expected_ids = [self.user_no_data.user_id, self.user_empty_data.user_id]
        self.assertCountEqual(results, expected_ids)

    def test_missing_user_data_property(self):
        results = (UserES()
                   .domain(self.domain)
                   .filter(_missing_user_data_property('location'))
                   .get_ids())

        expected_ids = [self.user_no_data.user_id, self.user_other_data.user_id]
        self.assertCountEqual(results, expected_ids)

    def test_empty_user_data_property(self):
        results = (UserES()
                   .domain(self.domain)
                   .filter(_empty_user_data_property('location'))
                   .get_ids())

        expected_ids = [self.user_empty_data.user_id]
        self.assertCountEqual(results, expected_ids)


@es_test(requires=[user_adapter], setup_class=True)
class TestIsActiveOnDomain(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.domain = 'TestUserDataFilters-1'
        cls.other_domain = 'TestUserDataFilters-2'
        for domain in [cls.domain, cls.other_domain]:
            domain_obj = create_domain(domain)
            cls.addClassCleanup(domain_obj.delete)

        cls.cc_user_active = cls.make_cc_user('cc_user_active', cls.domain)
        cls.cc_user_inactive = cls.make_cc_user('cc_user_inactive', cls.domain, is_active=False)
        cls.cc_user_active_other_domain = cls.make_cc_user('cc_user_active_other_domain', cls.other_domain)
        cls.cc_user_inactive_other_domain = cls.make_cc_user(
            'cc_user_inactive_other_domain', cls.other_domain, is_active=False)
        cls.web_user_active = cls.make_web_user('web_user_active', active_domains=[cls.domain])
        cls.web_user_inactive = cls.make_web_user('web_user_inactive', inactive_domains=[cls.domain])
        cls.web_user_active_other_domain = cls.make_web_user(
            'web_user_active_other_domain', active_domains=[cls.other_domain])
        cls.web_user_inactive_other_domain = cls.make_web_user(
            'web_user_inactive_other_domain', inactive_domains=[cls.other_domain])
        cls.web_user_active_both_domains = cls.make_web_user(
            'web_user_active_both_domains', active_domains=[cls.domain, cls.other_domain])
        cls.web_user_inactive_both_domains = cls.make_web_user(
            'web_user_inactive_both_domains', inactive_domains=[cls.domain, cls.other_domain])
        cls.web_user_active_inactive_other = cls.make_web_user(
            'web_user_active_inactive_other', active_domains=[cls.domain], inactive_domains=[cls.other_domain])
        cls.web_user_inactive_active_other = cls.make_web_user(
            'web_user_inactive_active_other', active_domains=[cls.other_domain], inactive_domains=[cls.domain])

    @classmethod
    def make_cc_user(cls, username, domain, is_active=True):
        user = CommCareUser.create(domain, username, "***********", None, None)
        user.is_active = is_active
        user_adapter.index(user, refresh=True)
        cls.addClassCleanup(user.delete, None, None)
        cls.addClassCleanup(user_adapter.delete, user._id)
        return user

    @classmethod
    def make_web_user(cls, username, *, active_domains=[], inactive_domains=[]):
        user = WebUser.create(None, username, "***********", None, None)
        for domain in active_domains:
            user.add_domain_membership(domain, is_active=True)
        for domain in inactive_domains:
            user.add_domain_membership(domain, is_active=False)
        user_adapter.index(user, refresh=True)
        cls.addClassCleanup(user.delete, None, None)
        cls.addClassCleanup(user_adapter.delete, user._id)
        return user

    def test_get_all(self):
        self.assertItemsEqual(
            UserES().show_inactive().values_list('username', flat=True),
            [
                'cc_user_active',
                'cc_user_inactive',
                'cc_user_active_other_domain',
                'cc_user_inactive_other_domain',
                'web_user_active',
                'web_user_inactive',
                'web_user_active_other_domain',
                'web_user_inactive_other_domain',
                'web_user_active_both_domains',
                'web_user_inactive_both_domains',
                'web_user_active_inactive_other',
                'web_user_inactive_active_other',
            ]
        )

    def test_get_active_in_domain(self):
        self.assertItemsEqual(
            UserES().domain(self.domain).has_domain_membership(self.domain, active=True)
            .values_list('username', flat=True),
            [
                'cc_user_active',
                'web_user_active',
                'web_user_active_both_domains',
                'web_user_active_inactive_other',
            ]
        )

    def test_get_inactive_in_domain(self):
        self.assertItemsEqual(
            UserES()
            .domain(self.domain)
            .show_inactive()
            .has_domain_membership(self.domain, active=False)
            .values_list('username', flat=True),
            [
                'cc_user_inactive',
                'web_user_inactive',
                'web_user_inactive_both_domains',
                'web_user_inactive_active_other',
            ]
        )

    def test_get_all_in_domain(self):
        self.assertItemsEqual(
            UserES().domain(self.domain).show_inactive().values_list('username', flat=True),
            [
                'cc_user_active',
                'cc_user_inactive',
                'web_user_active',
                'web_user_inactive',
                'web_user_active_both_domains',
                'web_user_inactive_both_domains',
                'web_user_active_inactive_other',
                'web_user_inactive_active_other',
            ]
        )
