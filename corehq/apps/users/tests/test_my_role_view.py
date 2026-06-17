from unittest.mock import patch

from django.test import TestCase

from corehq.apps.accounting.models import (
    BillingAccount,
    BillingAccountType,
    Currency,
)
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.users.models import HqPermissions, WebUser
from corehq.apps.users.models_role import UserRole
from corehq.apps.users.views.my_role import _build_my_role


class TestBuildMyRole(TestCase):
    domain = 'test-my-role'

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.domain_obj = create_domain(cls.domain)
        cls.addClassCleanup(cls.domain_obj.delete)

    def _make_user(self, username, role=None, is_admin=False, is_superuser=False):
        user = WebUser.create(self.domain, username, 'password', None, None)
        user.is_superuser = is_superuser
        if role:
            user.set_role(self.domain, role.get_qualified_id())
        elif is_admin:
            user.set_role(self.domain, 'admin')
        user.save()
        self.addCleanup(user.delete, self.domain, deleted_by=None)
        return user

    def test_regular_user_with_role_gets_role_label(self):
        role = UserRole.create(self.domain, 'App Editor')
        user = self._make_user('regular@test.com', role=role)

        result = _build_my_role(user, self.domain)

        assert result['role'] == 'App Editor'

    def test_regular_user_permissions_match_role(self):
        permissions = HqPermissions(edit_apps=True, view_apps=True)
        role = UserRole.create(self.domain, 'editor', permissions=permissions)
        user = self._make_user('editor@test.com', role=role)

        result = _build_my_role(user, self.domain)

        assert result['permissions']['edit_apps'] is True
        assert result['permissions']['view_apps'] is True
        assert result['permissions']['edit_web_users'] is False

    def test_permissions_dict_covers_every_known_permission(self):
        role = UserRole.create(self.domain, 'minimal')
        user = self._make_user('minimal@test.com', role=role)

        result = _build_my_role(user, self.domain)

        assert set(result['permissions'].keys()) == HqPermissions.permission_names()

    def test_parameterized_permission_with_partial_access_returns_object(self):
        permissions = HqPermissions(
            view_report_list=['report-id-1'],
            web_apps_list=['app-id-1', 'app-id-2'],
        )
        role = UserRole.create(self.domain, 'restricted', permissions=permissions)
        user = self._make_user('restricted@test.com', role=role)

        result = _build_my_role(user, self.domain)

        assert result['permissions']['view_reports'] == {
            'scope': 'limited', 'items': ['report-id-1'],
        }
        assert result['permissions']['access_web_apps'] == {
            'scope': 'limited', 'items': ['app-id-1', 'app-id-2'],
        }
        assert result['permissions']['view_tableau'] is False

    def test_parameterized_permission_with_no_access_returns_false(self):
        user = self._make_user('lurker-lists@test.com')

        result = _build_my_role(user, self.domain)

        assert result['permissions']['view_reports'] is False
        assert result['permissions']['view_tableau'] is False
        assert result['permissions']['access_web_apps'] is False
        assert result['permissions']['manage_data_registry'] is False
        assert result['permissions']['view_data_registry_contents'] is False
        assert result['permissions']['commcare_analytics_roles'] is False

    def test_domain_admin_flag_true_for_domain_admin(self):
        user = self._make_user('admin@test.com', is_admin=True)

        result = _build_my_role(user, self.domain)

        assert result['is_domain_admin'] is True
        for name in HqPermissions.permission_names():
            assert result['permissions'][name] is True

    def test_dimagi_admin_payload_is_only_the_flag(self):
        user = self._make_user('dimagi@test.com', is_superuser=True)

        result = _build_my_role(user, self.domain)

        assert result == {'is_dimagi_admin': True}

    def test_enterprise_admin_flag_true_when_email_listed(self):
        user = self._make_user('ent-admin@test.com')

        currency, _ = Currency.objects.get_or_create(code='USD')
        account = BillingAccount.objects.create(
            name='test-acct',
            currency=currency,
            account_type=BillingAccountType.GLOBAL_SERVICES,
            is_customer_billing_account=True,
            enterprise_admin_emails=[user.username],
        )
        self.addCleanup(account.delete)
        with patch.object(BillingAccount, 'get_account_by_domain', return_value=account):
            result = _build_my_role(user, self.domain)

        assert result['is_enterprise_admin'] is True
