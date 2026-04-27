from datetime import date, timedelta
from unittest.mock import patch

from django.contrib.messages import get_messages
from django.test import Client, TestCase
from django.urls import reverse
from django_prbac.models import Grant, Role, UserRole

from corehq import privileges
from corehq.apps.accounting.models import SoftwarePlanEdition
from corehq.apps.accounting.tests import generator as accounting_gen
from corehq.apps.accounting.tests.generator import generate_domain_subscription
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.enterprise.forms import (
    EnterpriseAdminForm,
    _get_sso_email_domains,
)
from corehq.apps.sso.models import (
    AuthenticatedEmailDomain,
    IdentityProvider,
    IdentityProviderType,
)
from corehq.apps.users.models import WebUser
from corehq.util.test_utils import flag_disabled, flag_enabled


def _noop(*args, **kwargs):
    pass


def _make_idp(account, slug, is_active=True, domains=None):
    idp = IdentityProvider.objects.create(
        owner=account,
        slug=slug,
        name=slug,
        idp_type=IdentityProviderType.ENTRA_ID,
        is_active=is_active,
    )
    for d in (domains or []):
        AuthenticatedEmailDomain.objects.create(
            email_domain=d, identity_provider=idp,
        )
    return idp


class GetSsoEmailDomainsTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.account = accounting_gen.billing_account(
            'admin@example.com', 'contact@example.com',
            is_customer_account=True,
        )

    def test_no_idp_returns_empty_set(self):
        assert _get_sso_email_domains(self.account) == set()

    def test_idp_without_domain_rows_returns_empty_set(self):
        _make_idp(self.account, slug='idp-a')
        assert _get_sso_email_domains(self.account) == set()

    def test_single_idp_with_domains(self):
        _make_idp(self.account, slug='idp-b', domains=['foo.com', 'bar.com'])
        assert _get_sso_email_domains(self.account) == {'foo.com', 'bar.com'}

    def test_multiple_active_idps_union_domains(self):
        _make_idp(self.account, slug='idp-c', domains=['foo.com'])
        _make_idp(self.account, slug='idp-d', domains=['baz.com'])
        assert _get_sso_email_domains(self.account) == {'foo.com', 'baz.com'}

    def test_inactive_idp_is_excluded(self):
        _make_idp(self.account, slug='idp-e', is_active=False,
                  domains=['inactive.com'])
        _make_idp(self.account, slug='idp-f', domains=['active.com'])
        assert _get_sso_email_domains(self.account) == {'active.com'}

    def test_domains_returned_lowercased(self):
        _make_idp(self.account, slug='idp-g', domains=['Mixed.Case.COM'])
        assert _get_sso_email_domains(self.account) == {'mixed.case.com'}


class EnterpriseAdminFormTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.account = accounting_gen.billing_account(
            'admin@example.com', 'contact@example.com',
            is_customer_account=True,
        )
        cls.account.enterprise_admin_emails = ['existing@example.com']
        cls.account.save()

    def _bind(self, email):
        return EnterpriseAdminForm({'email': email}, account=self.account)

    def test_valid_email_passes(self):
        form = self._bind('new@example.com')
        assert form.is_valid(), form.errors
        assert form.cleaned_data['email'] == 'new@example.com'

    def test_email_is_lowercased(self):
        form = self._bind('MixedCase@Example.com')
        assert form.is_valid(), form.errors
        assert form.cleaned_data['email'] == 'mixedcase@example.com'

    def test_invalid_email_format_rejected(self):
        form = self._bind('not-an-email')
        assert not form.is_valid()
        assert 'email' in form.errors

    def test_duplicate_email_rejected(self):
        form = self._bind('existing@example.com')
        assert not form.is_valid()
        assert 'already' in form.errors['email'][0]

    def test_duplicate_is_case_insensitive(self):
        form = self._bind('EXISTING@example.com')
        assert not form.is_valid()

    def test_no_sso_allows_any_domain(self):
        form = self._bind('someone@anywhere.com')
        assert form.is_valid(), form.errors

    def test_sso_restricts_email_domain(self):
        _make_idp(self.account, slug='idp-sso', domains=['corp.com'])
        form = self._bind('someone@other.com')
        assert not form.is_valid()
        assert 'not permitted' in form.errors['email'][0]

    def test_sso_allows_matching_domain(self):
        _make_idp(self.account, slug='idp-sso-ok', domains=['corp.com'])
        form = self._bind('someone@corp.com')
        assert form.is_valid(), form.errors

    def test_sso_without_domain_rows_allows_any_email(self):
        _make_idp(self.account, slug='idp-no-domains')
        form = self._bind('someone@unrestricted.com')
        assert form.is_valid(), form.errors


class _EnterpriseAdminViewTestBase(TestCase):
    """Shared fixture: a customer billing account, a linked domain, an
    existing enterprise admin WebUser, and the toggle enabled for that
    domain. Subclasses add behavior-specific fixtures."""

    @classmethod
    def setUpTestData(cls):
        cls.domain_name = 'ent-admin-test'
        cls.domain = create_domain(cls.domain_name)
        cls.account = accounting_gen.billing_account(
            'admin@example.com', 'contact@example.com',
            is_customer_account=True,
        )
        plan_version = accounting_gen.subscribable_plan_version(
            edition=SoftwarePlanEdition.ENTERPRISE,
        )
        start = date.today()
        # Kafka is not available in the test environment; stub the publish
        # call so fixture setup/teardown doesn't depend on a broker.
        with patch('corehq.apps.accounting.models.publish_domain_saved', _noop):
            generate_domain_subscription(
                cls.account, cls.domain,
                date_start=start,
                date_end=start + timedelta(days=365),
                plan_version=plan_version,
                is_active=True,
            )
        cls.admin_user = WebUser.create(
            cls.domain_name, 'admin-user@example.com', 'pw',
            None, None, is_admin=True,
        )
        cls.account.enterprise_admin_emails = [cls.admin_user.username]
        cls.account.save()

    def setUp(self):
        self.client = Client()
        self.client.login(
            username=self.admin_user.username, password='pw',
        )

    @classmethod
    def tearDownClass(cls):
        cls.admin_user.delete(cls.domain_name, deleted_by=None)
        # Kafka is not available in the test environment; stub the publish
        # call so fixture setup/teardown doesn't depend on a broker.
        with patch('corehq.apps.accounting.models.publish_domain_saved', _noop):
            cls.domain.delete()
        super().tearDownClass()

    @property
    def list_url(self):
        return reverse('enterprise_admins', args=[self.domain_name])

    def _reload_account(self):
        self.account.refresh_from_db()
        return self.account


class EnterpriseAdminsGetViewTests(_EnterpriseAdminViewTestBase):

    @flag_enabled('ENTERPRISE_ADMIN_SELF_SERVICE')
    def test_admin_can_load_page(self):
        response = self.client.get(self.list_url)
        assert response.status_code == 200
        self.assertContains(response, self.admin_user.username)

    @flag_disabled('ENTERPRISE_ADMIN_SELF_SERVICE')
    def test_toggle_disabled_returns_404(self):
        response = self.client.get(self.list_url)
        assert response.status_code == 404

    @flag_enabled('ENTERPRISE_ADMIN_SELF_SERVICE')
    def test_non_admin_user_gets_404(self):
        outsider = WebUser.create(
            self.domain_name, 'outsider@example.com', 'pw',
            None, None,
        )
        self.addCleanup(outsider.delete, self.domain_name, deleted_by=None)
        self.client.login(username=outsider.username, password='pw')
        response = self.client.get(self.list_url)
        assert response.status_code == 404

    @flag_enabled('ENTERPRISE_ADMIN_SELF_SERVICE')
    def test_ops_user_with_accounting_admin_can_load_page(self):
        # Users with ACCOUNTING_ADMIN (Ops) can view the admin list even if
        # they aren't listed in enterprise_admin_emails. Exercises the Ops
        # branch of request_has_permissions_for_enterprise_admin.
        ops_user = WebUser.create(
            self.domain_name, 'ops@example.com', 'pw',
            None, None,
        )
        self.addCleanup(ops_user.delete, self.domain_name, deleted_by=None)
        # Grant ACCOUNTING_ADMIN via OPERATIONS_TEAM role — same pattern used
        # in corehq/apps/hqadmin/tests/test_views.py::_make_accounting_admin.
        django_user = ops_user.get_django_user()
        ops_role, _ = Role.objects.get_or_create(
            slug=privileges.OPERATIONS_TEAM, defaults={'name': 'Ops'},
        )
        accounting_role, _ = Role.objects.get_or_create(
            slug=privileges.ACCOUNTING_ADMIN,
            defaults={'name': 'Accounting'},
        )
        Grant.objects.get_or_create(
            from_role=ops_role, to_role=accounting_role,
        )
        user_privs = Role.objects.create(
            slug=f'{django_user.username}_privs',
            name='Test user privileges',
        )
        UserRole.objects.create(user=django_user, role=user_privs)
        Grant.objects.create(from_role=user_privs, to_role=ops_role)
        Role.update_cache()

        self.client.login(username=ops_user.username, password='pw')
        response = self.client.get(self.list_url)
        assert response.status_code == 200
        self.assertContains(response, self.admin_user.username)


class AddEnterpriseAdminViewTests(_EnterpriseAdminViewTestBase):

    @property
    def add_url(self):
        return reverse('add_enterprise_admin', args=[self.domain_name])

    @flag_enabled('ENTERPRISE_ADMIN_SELF_SERVICE')
    def test_add_valid_email_appends_lowercased(self):
        response = self.client.post(
            self.add_url, {'email': 'NewAdmin@Example.com'},
        )
        self.assertRedirects(response, self.list_url)
        account = self._reload_account()
        assert 'newadmin@example.com' in account.enterprise_admin_emails

    @flag_enabled('ENTERPRISE_ADMIN_SELF_SERVICE')
    def test_add_duplicate_email_is_rejected(self):
        response = self.client.post(
            self.add_url, {'email': self.admin_user.username},
        )
        self.assertRedirects(response, self.list_url)
        account = self._reload_account()
        count = account.enterprise_admin_emails.count(self.admin_user.username)
        assert count == 1
        msgs = [str(m) for m in get_messages(response.wsgi_request)]
        assert any('already' in m for m in msgs)

    @flag_enabled('ENTERPRISE_ADMIN_SELF_SERVICE')
    def test_add_invalid_format_is_rejected(self):
        response = self.client.post(self.add_url, {'email': 'not-an-email'})
        self.assertRedirects(response, self.list_url)
        account = self._reload_account()
        assert 'not-an-email' not in account.enterprise_admin_emails

    @flag_enabled('ENTERPRISE_ADMIN_SELF_SERVICE')
    def test_add_respects_sso_domain_restriction(self):
        _make_idp(self.account, slug='idp-sso', domains=['corp.com'])
        response = self.client.post(
            self.add_url, {'email': 'x@other.com'},
        )
        self.assertRedirects(response, self.list_url)
        account = self._reload_account()
        assert 'x@other.com' not in account.enterprise_admin_emails
        msgs = [str(m) for m in get_messages(response.wsgi_request)]
        assert any('not permitted' in m for m in msgs)

    @flag_enabled('ENTERPRISE_ADMIN_SELF_SERVICE')
    def test_add_logs_info(self):
        with self.assertLogs(
            'corehq.apps.enterprise.views', level='INFO'
        ) as cap:
            self.client.post(
                self.add_url, {'email': 'logger@example.com'},
            )
        assert any('logger@example.com' in line for line in cap.output)

    @flag_disabled('ENTERPRISE_ADMIN_SELF_SERVICE')
    def test_add_toggle_disabled_returns_404(self):
        response = self.client.post(
            self.add_url, {'email': 'blocked@example.com'},
        )
        assert response.status_code == 404
        account = self._reload_account()
        assert 'blocked@example.com' not in account.enterprise_admin_emails


class RemoveEnterpriseAdminViewTests(_EnterpriseAdminViewTestBase):

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.second_admin = WebUser.create(
            cls.domain_name, 'second-admin@example.com', 'pw',
            None, None, is_admin=True,
        )
        cls.account.enterprise_admin_emails = [
            cls.admin_user.username,
            cls.second_admin.username,
        ]
        cls.account.save()

    @classmethod
    def tearDownClass(cls):
        cls.second_admin.delete(cls.domain_name, deleted_by=None)
        super().tearDownClass()

    @property
    def remove_url(self):
        return reverse('remove_enterprise_admin', args=[self.domain_name])

    @flag_enabled('ENTERPRISE_ADMIN_SELF_SERVICE')
    def test_remove_peer_admin(self):
        response = self.client.post(
            self.remove_url, {'email': self.second_admin.username},
        )
        self.assertRedirects(response, self.list_url)
        account = self._reload_account()
        assert self.second_admin.username not in account.enterprise_admin_emails
        assert self.admin_user.username in account.enterprise_admin_emails

    @flag_enabled('ENTERPRISE_ADMIN_SELF_SERVICE')
    def test_remove_self_is_blocked(self):
        response = self.client.post(
            self.remove_url, {'email': self.admin_user.username},
        )
        self.assertRedirects(response, self.list_url)
        account = self._reload_account()
        assert self.admin_user.username in account.enterprise_admin_emails
        msgs = [str(m) for m in get_messages(response.wsgi_request)]
        assert any('yourself' in m for m in msgs)

    @flag_enabled('ENTERPRISE_ADMIN_SELF_SERVICE')
    def test_remove_last_admin_is_blocked(self):
        # Reduce the admin list to a single entry (the current user, so
        # require_enterprise_admin still passes), then try to remove a
        # different email. The self-removal guard passes (target != self),
        # then the last-admin guard trips.
        self.account.enterprise_admin_emails = [self.admin_user.username]
        self.account.save()

        response = self.client.post(
            self.remove_url, {'email': 'someone-else@example.com'},
        )
        self.assertRedirects(response, self.list_url)
        account = self._reload_account()
        assert account.enterprise_admin_emails == [self.admin_user.username]
        msgs = [str(m) for m in get_messages(response.wsgi_request)]
        assert any('at least one' in m for m in msgs)

    @flag_enabled('ENTERPRISE_ADMIN_SELF_SERVICE')
    def test_remove_unknown_email_reports_error(self):
        response = self.client.post(
            self.remove_url, {'email': 'ghost@example.com'},
        )
        self.assertRedirects(response, self.list_url)
        msgs = [str(m) for m in get_messages(response.wsgi_request)]
        assert any('is not an enterprise administrator' in m for m in msgs)

    @flag_enabled('ENTERPRISE_ADMIN_SELF_SERVICE')
    def test_remove_is_case_insensitive(self):
        response = self.client.post(
            self.remove_url,
            {'email': self.second_admin.username.upper()},
        )
        self.assertRedirects(response, self.list_url)
        account = self._reload_account()
        assert self.second_admin.username not in account.enterprise_admin_emails

    @flag_enabled('ENTERPRISE_ADMIN_SELF_SERVICE')
    def test_remove_logs_info(self):
        with self.assertLogs(
            'corehq.apps.enterprise.views', level='INFO',
        ) as cap:
            self.client.post(
                self.remove_url, {'email': self.second_admin.username},
            )
        assert any(self.second_admin.username in line for line in cap.output)

    @flag_disabled('ENTERPRISE_ADMIN_SELF_SERVICE')
    def test_remove_toggle_disabled_returns_404(self):
        response = self.client.post(
            self.remove_url, {'email': self.second_admin.username},
        )
        assert response.status_code == 404

    @flag_enabled('ENTERPRISE_ADMIN_SELF_SERVICE')
    def test_remove_missing_email_reports_error(self):
        response = self.client.post(self.remove_url, {})
        self.assertRedirects(response, self.list_url)
        account = self._reload_account()
        assert sorted(account.enterprise_admin_emails) == sorted(
            [self.admin_user.username, self.second_admin.username]
        )
        msgs = [str(m) for m in get_messages(response.wsgi_request)]
        assert any('is not an enterprise administrator' in m for m in msgs)
