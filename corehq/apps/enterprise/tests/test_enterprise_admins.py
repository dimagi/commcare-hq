from django.test import TestCase

from corehq.apps.accounting.tests import generator as accounting_gen
from corehq.apps.enterprise.forms import _get_sso_email_domains
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
