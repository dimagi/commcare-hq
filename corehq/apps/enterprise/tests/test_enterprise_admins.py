from django.test import TestCase

from corehq.apps.accounting.tests import generator as accounting_gen
from corehq.apps.enterprise.forms import EnterpriseAdminForm, _get_sso_email_domains
from corehq.apps.sso.models import (
    AuthenticatedEmailDomain,
    IdentityProvider,
    IdentityProviderType,
)


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
        self.assertEqual(_get_sso_email_domains(self.account), set())

    def test_idp_without_domain_rows_returns_empty_set(self):
        _make_idp(self.account, slug='idp-a')
        self.assertEqual(_get_sso_email_domains(self.account), set())

    def test_single_idp_with_domains(self):
        _make_idp(self.account, slug='idp-b', domains=['foo.com', 'bar.com'])
        self.assertEqual(
            _get_sso_email_domains(self.account),
            {'foo.com', 'bar.com'},
        )

    def test_multiple_active_idps_union_domains(self):
        _make_idp(self.account, slug='idp-c', domains=['foo.com'])
        _make_idp(self.account, slug='idp-d', domains=['baz.com'])
        self.assertEqual(
            _get_sso_email_domains(self.account),
            {'foo.com', 'baz.com'},
        )

    def test_inactive_idp_is_excluded(self):
        _make_idp(self.account, slug='idp-e', is_active=False,
                  domains=['inactive.com'])
        _make_idp(self.account, slug='idp-f', domains=['active.com'])
        self.assertEqual(
            _get_sso_email_domains(self.account),
            {'active.com'},
        )

    def test_domains_returned_lowercased(self):
        _make_idp(self.account, slug='idp-g', domains=['Mixed.Case.COM'])
        self.assertEqual(
            _get_sso_email_domains(self.account),
            {'mixed.case.com'},
        )


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
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data['email'], 'new@example.com')

    def test_email_is_lowercased(self):
        form = self._bind('MixedCase@Example.com')
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data['email'], 'mixedcase@example.com')

    def test_invalid_email_format_rejected(self):
        form = self._bind('not-an-email')
        self.assertFalse(form.is_valid())
        self.assertIn('email', form.errors)

    def test_duplicate_email_rejected(self):
        form = self._bind('existing@example.com')
        self.assertFalse(form.is_valid())
        self.assertIn('already', form.errors['email'][0])

    def test_duplicate_is_case_insensitive(self):
        form = self._bind('EXISTING@example.com')
        self.assertFalse(form.is_valid())

    def test_no_sso_allows_any_domain(self):
        form = self._bind('someone@anywhere.com')
        self.assertTrue(form.is_valid(), form.errors)

    def test_sso_restricts_email_domain(self):
        _make_idp(self.account, slug='idp-sso', domains=['corp.com'])
        form = self._bind('someone@other.com')
        self.assertFalse(form.is_valid())
        self.assertIn('not permitted', form.errors['email'][0])

    def test_sso_allows_matching_domain(self):
        _make_idp(self.account, slug='idp-sso-ok', domains=['corp.com'])
        form = self._bind('someone@corp.com')
        self.assertTrue(form.is_valid(), form.errors)

    def test_sso_without_domain_rows_allows_any_email(self):
        _make_idp(self.account, slug='idp-no-domains')
        form = self._bind('someone@unrestricted.com')
        self.assertTrue(form.is_valid(), form.errors)
