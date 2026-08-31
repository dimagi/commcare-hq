from datetime import date

from django.contrib.auth.models import User
from django.test import SimpleTestCase, TestCase
from django_prbac.models import Grant, Role, UserRole

from corehq import privileges
from corehq.apps.accounting.utils import (
    get_accounting_admin_users,
    is_date_range_overlapping,
)


class TestIsDateRangeOverlapping(SimpleTestCase):
    def test_first_range_is_contained_in_second_range(self):
        assert is_date_range_overlapping(date(2025, 1, 3), date(2025, 1, 6),
                                         date(2025, 1, 1), date(2025, 1, 10))

    def test_second_range_is_contained_in_first_range(self):
        assert is_date_range_overlapping(date(2025, 1, 1), date(2025, 1, 10),
                                         date(2025, 1, 5), date(2025, 1, 7))

    def test_partial_overlap_start(self):
        assert is_date_range_overlapping(date(2025, 1, 1), date(2025, 1, 10),
                                         date(2024, 12, 20), date(2025, 1, 2))

    def test_partial_overlap_end(self):
        assert is_date_range_overlapping(date(2025, 1, 1), date(2025, 1, 10),
                                         date(2025, 1, 9), date(2025, 1, 20))

    def test_exact_overlap(self):
        assert is_date_range_overlapping(date(2025, 1, 1), date(2025, 1, 10),
                                         date(2025, 1, 1), date(2025, 1, 10))

    def test_no_overlap_before(self):
        assert not is_date_range_overlapping(date(2025, 1, 10), date(2025, 1, 20),
                                             date(2025, 1, 1), date(2025, 1, 9))

    def test_no_overlap_after(self):
        assert not is_date_range_overlapping(date(2025, 1, 1), date(2025, 1, 9),
                                             date(2025, 1, 10), date(2025, 1, 20))

    def test_adjacent_ranges_do_not_overlap(self):
        # Two ranges that touch at a boundary is not considered an overlap.
        # This is a special case for our accounting system
        assert not is_date_range_overlapping(date(2025, 1, 1), date(2025, 1, 10),
                                             date(2025, 1, 10), date(2025, 1, 20))

        assert not is_date_range_overlapping(date(2025, 1, 10), date(2025, 1, 20),
                                             date(2025, 1, 1), date(2025, 1, 10))

    def test_same_start_date_is_overlap(self):
        assert is_date_range_overlapping(date(2025, 1, 5), date(2025, 1, 10),
                                         date(2025, 1, 5), date(2025, 1, 15))

    def test_same_end_date_is_overlap(self):
        assert is_date_range_overlapping(date(2025, 1, 1), date(2025, 1, 10),
                                         date(2025, 1, 5), date(2025, 1, 10))

    def test_first_range_infinite_end(self):
        assert is_date_range_overlapping(date(2025, 1, 1), None,
                                         date(2025, 1, 10), date(2025, 1, 20))

    def test_second_range_infinite_end(self):
        assert is_date_range_overlapping(date(2025, 1, 10), date(2025, 1, 20),
                                         date(2025, 1, 1), None)

    def test_both_ranges_infinite_end(self):
        assert is_date_range_overlapping(date(2025, 1, 1), None,
                                         date(2025, 2, 1), None)

    def test_first_range_infinite_end_but_start_after_second_range_end(self):
        assert not is_date_range_overlapping(date(2025, 1, 1), None,
                                             date(2024, 1, 1), date(2024, 12, 31))

    def test_second_range_infinite_end_but_start_after_first_range_end(self):
        assert not is_date_range_overlapping(date(2024, 1, 1), date(2024, 12, 31),
                                             date(2025, 1, 1), None)


class TestGetAccountingAdminUsers(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.accounting_role, _ = Role.objects.get_or_create(
            slug=privileges.ACCOUNTING_ADMIN, defaults={'name': 'Accounting Admin'}
        )
        cls.ops_role, _ = Role.objects.get_or_create(
            slug=privileges.OPERATIONS_TEAM, defaults={'name': 'Dimagi Operations Team'}
        )
        Grant.objects.get_or_create(from_role=cls.ops_role, to_role=cls.accounting_role)

    def _create_user_with_privilege_role(self, username, grant_to=None):
        user = User.objects.create(username=username)
        user_privs = Role.objects.create(
            slug=f'{username}_privileges', name=f'Privileges for {username}'
        )
        UserRole.objects.create(user=user, role=user_privs)
        if grant_to is not None:
            Grant.objects.create(from_role=user_privs, to_role=grant_to)
        Role.update_cache()
        return user

    def test_includes_user_granted_via_operations_team(self):
        user = self._create_user_with_privilege_role('ops@dimagi.com', grant_to=self.ops_role)
        assert not user.is_superuser
        assert user in get_accounting_admin_users()

    def test_includes_user_with_direct_grant(self):
        user = self._create_user_with_privilege_role('direct@dimagi.com', grant_to=self.accounting_role)
        assert user in get_accounting_admin_users()

    def test_excludes_user_without_accounting_privilege(self):
        user = self._create_user_with_privilege_role('other@dimagi.com')
        assert user not in get_accounting_admin_users()

    def test_excludes_user_without_privilege_role(self):
        user = User.objects.create(username='plain@dimagi.com')
        assert user not in get_accounting_admin_users()
