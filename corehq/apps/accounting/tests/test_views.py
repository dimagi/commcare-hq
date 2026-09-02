from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse
from django_prbac.models import Grant, Role, UserRole

from corehq import privileges
from corehq.apps.accounting.views import ManageAccountingAdminsView
from corehq.apps.users.models import WebUser


def _grant_accounting_admin(django_user):
    # privileges.ACCOUNTING_ADMIN is applied via OPERATIONS_TEAM role
    ops_role, _ = Role.objects.get_or_create(slug=privileges.OPERATIONS_TEAM, defaults={'name': 'Ops'})
    accounting_role, _ = Role.objects.get_or_create(
        slug=privileges.ACCOUNTING_ADMIN, defaults={'name': 'Accounting'}
    )
    Grant.objects.get_or_create(from_role=ops_role, to_role=accounting_role)
    user_privs = Role.objects.create(slug=f"{django_user.username}_privs", name="Test user privileges")
    UserRole.objects.create(user=django_user, role=user_privs)
    Grant.objects.create(from_role=user_privs, to_role=ops_role)
    Role.update_cache()


class TestAccountingAdminAccess(TestCase):
    """Accounting pages require the ACCOUNTING_ADMIN privilege, but not
    superuser status."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.accounting_admin = WebUser.create(
            None, "acct-admin@dimagi.com", "password", None, None
        )
        cls.addClassCleanup(cls.accounting_admin.delete, None, None)
        _grant_accounting_admin(cls.accounting_admin.get_django_user())

        cls.plain_user = WebUser.create(
            None, "plain@dimagi.com", "password", None, None
        )
        cls.addClassCleanup(cls.plain_user.delete, None, None)

        cls.superuser_without_privilege = WebUser.create(
            None, "superuser@dimagi.com", "password", None, None, is_superuser=True
        )
        cls.addClassCleanup(cls.superuser_without_privilege.delete, None, None)

        cls.default_url = reverse('accounting_default')
        cls.section_url = reverse(ManageAccountingAdminsView.urlname)

    def test_non_superuser_accounting_admin_can_access_default_view(self):
        self.client.login(username=self.accounting_admin.username, password='password')
        response = self.client.get(self.default_url)
        assert response.status_code == 302
        assert response.url != reverse('no_permissions')

    def test_non_superuser_accounting_admin_can_access_section_view(self):
        self.client.login(username=self.accounting_admin.username, password='password')
        response = self.client.get(self.section_url)
        assert response.status_code == 200

    def test_user_without_privilege_gets_404(self):
        self.client.login(username=self.plain_user.username, password='password')
        response = self.client.get(self.default_url)
        assert response.status_code == 404

    def test_superuser_without_privilege_gets_404(self):
        self.client.login(username=self.superuser_without_privilege.username, password='password')
        response = self.client.get(self.default_url)
        assert response.status_code == 404

    def test_anonymous_user_is_redirected_to_login(self):
        response = self.client.get(self.default_url)
        assert response.status_code == 302
        assert response.url.startswith('/accounts/login/')

    def test_sso_authenticated_session_is_blocked(self):
        self.client.login(username=self.accounting_admin.username, password='password')
        with patch(
            'corehq.apps.accounting.decorators.is_request_using_sso',
            return_value=True,
        ):
            response = self.client.get(self.default_url)
        assert response.status_code == 302
        assert response.url == reverse('no_permissions')
