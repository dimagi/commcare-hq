import datetime
from unittest.mock import patch
from corehq.apps.accounting.models import SoftwarePlanEdition
from corehq.apps.accounting.tests import generator as accounting_generator
from corehq.apps.domain.models import Domain
from corehq.apps.sso.models import (
    AuthenticatedEmailDomain,
    IdentityProvider,
    LoginEnforcementType,
    SsoTestUser,
    UserExemptFromSingleSignOn,
)
from corehq.apps.sso.tests import generator
from corehq.apps.users.models import WebUser

from django.test import TestCase


class IdentityProviderTests(TestCase):
    @patch('corehq.apps.sso.tasks.update_sso_user_api_key_expiration_dates')
    def test_more_restrictive_api_key_expiration_date_updates_api_key_expirations(self, mock_task):
        idp = self._create_identity_provider(max_days_until_user_api_key_expiration=None)

        idp.max_days_until_user_api_key_expiration = 30
        idp.save()

        mock_task.delay.assert_called()

    @patch('corehq.apps.sso.tasks.update_sso_user_api_key_expiration_dates')
    def test_unchanged_api_key_expiration_does_not_call_task(self, mock_task):
        idp = self._create_identity_provider(max_days_until_user_api_key_expiration=30)

        idp.max_days_until_user_api_key_expiration = 30
        idp.save()

        mock_task.delay.assert_not_called()

    @patch('corehq.apps.sso.tasks.update_sso_user_api_key_expiration_dates')
    def test_less_restrictive_api_key_expiration_date_does_not_call_task(self, mock_task):
        idp = self._create_identity_provider(max_days_until_user_api_key_expiration=30)

        idp.max_days_until_user_api_key_expiration = 60
        idp.save()

        mock_task.delay.assert_not_called()

    @patch('corehq.apps.sso.tasks.update_sso_user_api_key_expiration_dates')
    def test_removing_max_api_expiration_does_not_call_task(self, mock_task):
        idp = self._create_identity_provider(max_days_until_user_api_key_expiration=30)

        idp.max_days_until_user_api_key_expiration = None
        idp.save()

        mock_task.delay.assert_not_called()

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.billing_account = generator.get_billing_account_for_idp()

    def _create_identity_provider(self, max_days_until_user_api_key_expiration=None):
        return IdentityProvider.objects.create(
            owner=self.billing_account,
            name='Test IDP',
            slug='testidp',
            created_by='admin@dimagi.com',
            last_modified_by='admin@dimagi.com',
            max_days_until_user_api_key_expiration=max_days_until_user_api_key_expiration,
        )


class IdentityProviderGovernanceScopeTests(TestCase):
    @classmethod
    def setUpClass(cls):

        super().setUpClass()
        cls.email_domain_str = 'vaultwax.com'

        cls.account = generator.get_billing_account_for_idp()
        cls.account.enterprise_admin_emails = [f'admin@{cls.email_domain_str}']
        cls.account.save()
        cls.domain = Domain.get_or_create_with_name("vaultwax-001", is_active=True)
        cls.addClassCleanup(cls.domain.delete)

        enterprise_plan = accounting_generator.subscribable_plan_version(edition=SoftwarePlanEdition.ENTERPRISE)
        accounting_generator.generate_domain_subscription(
            cls.account,
            cls.domain,
            date_start=datetime.date.today(),
            date_end=None,
            plan_version=enterprise_plan,
            is_active=True,
        )

    def setUp(self):
        super().setUp()
        self.idp = generator.create_idp('vaultwax', self.account)
        self.email_domain = AuthenticatedEmailDomain.objects.create(
            email_domain=self.email_domain_str,
            identity_provider=self.idp,
        )

        self.web_user_a = self._create_web_user(f'a@{self.email_domain_str}')
        self.web_user_b = self._create_web_user(f'b@{self.email_domain_str}')
        self.web_user_c = self._create_web_user(f'c@{self.email_domain_str}')
        self.test_user_a = self._create_test_sso_user(f'test_a@{self.email_domain_str}')
        self.test_user_b = self._create_test_sso_user(f'test_b@{self.email_domain_str}')

    def _create_web_user(self, username):
        user = WebUser.create(
            self.domain.name, username, 'testpwd', None, None
        )
        self.addCleanup(user.delete, self.domain.name, deleted_by=None)
        return user

    def _create_test_sso_user(self, username):
        SsoTestUser.objects.create(
            email_domain=self.email_domain,
            username=username,
        )
        return self._create_web_user(username)

    def test_idp_governance_scope_returns_everyone_when_login_enforcement_is_global(self):
        self.assertCountEqual(self.idp.get_local_member_usernames(),
                              [self.web_user_a.username, self.web_user_b.username, self.web_user_c.username,
                               self.test_user_a.username, self.test_user_b.username])

    def test_idp_governance_scope_returns_test_user_only_when_login_enforcement_is_test(self):
        self.idp.login_enforcement_type = LoginEnforcementType.TEST
        self.idp.save()

        self.assertCountEqual(self.idp.get_local_member_usernames(),
                              [self.test_user_a.username, self.test_user_b.username])

    def test_idp_governance_scope_excludes_exempt_user(self):
        # exempt user cannot be test user, so this idp must be in global mode
        UserExemptFromSingleSignOn.objects.create(
            email_domain=self.email_domain,
            username=f'exempt{self.email_domain}'
        )
        self.assertCountEqual(self.idp.get_local_member_usernames(),
                              [self.web_user_a.username, self.web_user_b.username, self.web_user_c.username,
                               self.test_user_a.username, self.test_user_b.username])

    def test_idp_governance_scope_excludes_users_have_different_email_domain(self):
        self.other_email_domain_user = self._create_web_user('a@gmail.com')

        self.assertCountEqual(self.idp.get_local_member_usernames(),
                              [self.web_user_a.username, self.web_user_b.username, self.web_user_c.username,
                               self.test_user_a.username, self.test_user_b.username])
