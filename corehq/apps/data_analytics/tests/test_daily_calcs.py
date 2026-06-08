from datetime import date, timedelta

from django.test import TestCase

from time_machine import travel

from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.es.tests.utils import es_test
from corehq.apps.es.users import user_adapter
from corehq.apps.users.dbaccessors import delete_all_users
from corehq.apps.users.models import WebUser

from ..daily_calcs import (
    _calc_web_users_accessed_30d,
)
from ..metric_registry import DomainContext


@es_test(requires=[user_adapter])
@travel('2026-06-08', tick=False)
class TestCalcWebUsersAccessed30d(TestCase):

    def setUp(self):
        super().setUp()
        self.domain_obj = create_domain('web-access-test')
        self.addCleanup(self.domain_obj.delete)

    def tearDown(self):
        delete_all_users
        super().tearDown()

    def _make_web_user(self, name, domain, last_accessed):
        user = WebUser.create(
            domain=domain,
            username=f'{name}@example.com',
            password='Passw0rd!',
            created_by=None,
            created_via=None,
        )
        if last_accessed is not None:
            user.get_domain_membership(domain).last_accessed = last_accessed
            user.save()
        user_adapter.index(user, refresh=True)
        return user

    def test_counts_web_users_accessed_in_last_30_days(self):
        today = date.today()
        self._make_web_user('recent', self.domain_obj.name, today)
        assert _calc_web_users_accessed_30d(DomainContext(self.domain_obj)) == 1

    def test_counts_web_users_accessed_30_days_ago(self):
        today = date.today()
        self._make_web_user('30_days', self.domain_obj.name, today - timedelta(days=30))
        assert _calc_web_users_accessed_30d(DomainContext(self.domain_obj)) == 1

    def test_excludes_web_users_accessed_31_days_ago(self):
        today = date.today()
        self._make_web_user('31_days', self.domain_obj.name, today - timedelta(days=31))
        assert _calc_web_users_accessed_30d(DomainContext(self.domain_obj)) == 0

    def test_excludes_web_users_never_accessed(self):
        self._make_web_user('never', self.domain_obj.name, None)
        assert _calc_web_users_accessed_30d(DomainContext(self.domain_obj)) == 0

    def test_excludes_web_users_only_accessed_other_domain(self):
        today = date.today()
        other_domain_obj = create_domain('web-access-other')
        self.addCleanup(other_domain_obj.delete)

        # Active only in another domain -> excluded by the domain filter.
        other_domain_user = self._make_web_user('elsewhere', 'web-access-other', today)
        other_domain_user.add_domain_membership('web-access-test')

        assert _calc_web_users_accessed_30d(DomainContext(self.domain_obj)) == 0
