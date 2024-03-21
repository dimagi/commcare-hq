import datetime
from unittest.mock import ANY, patch

from django.test import TestCase
from freezegun import freeze_time

from corehq.apps.accounting.models import SoftwarePlanEdition
from corehq.apps.accounting.tests import generator as accounting_generator
from corehq.apps.domain.models import Domain
from corehq.apps.sso.certificates import DEFAULT_EXPIRATION
from corehq.apps.sso.models import AuthenticatedEmailDomain, IdentityProviderType, UserExemptFromSingleSignOn
from corehq.apps.sso.tasks import (
    IDP_CERT_EXPIRES_REMINDER_DAYS,
    auto_deactivate_removed_sso_users,
    idp_cert_expires_reminder,
    renew_service_provider_x509_certificates,
    create_rollover_service_provider_x509_certificates,
    send_api_token_expiration_reminder,
)
from corehq.apps.sso.tests import generator
from corehq.apps.users.models import WebUser


def _get_days_before_expiration(days_before):
    return (DEFAULT_EXPIRATION / (24 * 60 * 60)) - days_before


class TestSSOTasks(TestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.account = generator.get_billing_account_for_idp()

    def setUp(self):
        super().setUp()
        self.idp = generator.create_idp('vaultwax', self.account)

    def test_create_rollover_service_provider_x509_certificates(self):
        self.idp.create_service_provider_certificate()
        self.idp.date_sp_cert_expiration = (
            datetime.datetime.utcnow()
            - datetime.timedelta(days=_get_days_before_expiration(13))
        )
        self.idp.save()

        sp_cert_public = self.idp.sp_cert_public
        sp_cert_private = self.idp.sp_cert_private
        date_sp_cert_expiration = self.idp.date_sp_cert_expiration

        create_rollover_service_provider_x509_certificates()
        self.idp.refresh_from_db()

        # make sure the active SP cert was not changed
        self.assertEqual(self.idp.sp_cert_public, sp_cert_public)
        self.assertEqual(self.idp.sp_cert_private, sp_cert_private)
        self.assertEqual(self.idp.date_sp_cert_expiration, date_sp_cert_expiration)

        # make sure that the rollover cert was generated
        self.assertIsNotNone(self.idp.sp_rollover_cert_public)
        self.assertIsNotNone(self.idp.sp_rollover_cert_private)
        self.assertIsNotNone(self.idp.date_sp_rollover_cert_expiration)

        # ...and has the expected expiration date based on DEFAULT_EXPIRATION
        approx_expiration = datetime.datetime.utcnow() + datetime.timedelta(
            days=_get_days_before_expiration(1)
        )
        self.assertGreater(self.idp.date_sp_rollover_cert_expiration, approx_expiration)

    def test_renew_service_provider_x509_certificates(self):
        self.idp.create_service_provider_certificate()
        self.idp.create_rollover_service_provider_certificate()
        self.idp.date_sp_cert_expiration = (
            datetime.datetime.utcnow()
            - datetime.timedelta(seconds=_get_days_before_expiration(7))
        )
        self.idp.save()

        new_cert_public = self.idp.sp_rollover_cert_public
        new_cert_private = self.idp.sp_rollover_cert_private
        new_cert_expiration = self.idp.date_sp_rollover_cert_expiration

        renew_service_provider_x509_certificates()
        self.idp.refresh_from_db()

        # make sure that rollover SP cert fields are now null
        self.assertIsNone(self.idp.sp_rollover_cert_public)
        self.assertIsNone(self.idp.sp_rollover_cert_private)
        self.assertIsNone(self.idp.date_sp_rollover_cert_expiration)

        # make sure rollover SP cert was properly transferred to active SP cert
        self.assertEqual(self.idp.sp_cert_public, new_cert_public)
        self.assertEqual(self.idp.sp_cert_private, new_cert_private)
        self.assertEqual(
            self.idp.date_sp_cert_expiration.replace(tzinfo=None),
            new_cert_expiration.replace(tzinfo=None)
        )

    def assert_idp_cert_expires_reminder(self, assert_reminder, remind_days=IDP_CERT_EXPIRES_REMINDER_DAYS):
        # setup account attrs
        recipient = "admin@example.com"
        self.account.enterprise_admin_emails = [recipient]
        self.account.save()
        # configure idp expiration date
        expires = datetime.datetime.utcnow()
        self.idp.date_idp_cert_expiration = expires
        self.idp.save()
        # test alerts
        for num_days in remind_days:
            with freeze_time(expires - datetime.timedelta(days=num_days)):
                with patch("corehq.apps.sso.tasks.send_html_email_async.delay") as mock_send:
                    idp_cert_expires_reminder()
                    if assert_reminder:
                        mock_send.assert_called_once_with(ANY, recipient, ANY,
                            text_content=ANY, email_from=ANY, bcc=ANY)
                    else:
                        mock_send.assert_not_called()

    def set_idp_active(self, active):
        self.idp.is_active = active
        self.idp.save()

    def test_idp_cert_expires_reminder(self):
        self.set_idp_active(True)
        self.assert_idp_cert_expires_reminder(True)

    def test_idp_cert_expires_reminder_60(self):
        self.set_idp_active(True)
        self.assert_idp_cert_expires_reminder(False, [60])

    def test_idp_cert_expires_reminder_inactive(self):
        self.set_idp_active(False)
        self.assert_idp_cert_expires_reminder(False)

    def _assert_idp_secret_expires_reminder(self, assert_reminder, remind_days=IDP_CERT_EXPIRES_REMINDER_DAYS):
        # setup account attrs
        recipient = "admin@example.com"
        self.account.enterprise_admin_emails = [recipient]
        self.account.save()
        # configure idp expiration date
        expires = datetime.datetime.utcnow()
        self.idp.date_api_secret_expiration = expires
        # configure idp auto-deactivation
        self.idp.enable_user_deactivation = True
        self.idp.save()
        # test alerts
        for num_days in remind_days:
            with freeze_time(expires - datetime.timedelta(days=num_days)):
                with patch("corehq.apps.sso.tasks.send_html_email_async.delay") as mock_send:
                    send_api_token_expiration_reminder()
                    if assert_reminder:
                        mock_send.assert_called_once_with(ANY, recipient, ANY,
                            text_content=ANY, email_from=ANY, bcc=ANY)
                    else:
                        mock_send.assert_not_called()

    def test_idp_secret_expires_reminder(self):
        self.set_idp_active(True)
        self._assert_idp_secret_expires_reminder(True)

    def test_idp_secret_expires_reminder_60(self):
        self.set_idp_active(True)
        self._assert_idp_secret_expires_reminder(False, [60])

    def test_idp_secret_expires_reminder_inactive(self):
        self.set_idp_active(False)
        self._assert_idp_secret_expires_reminder(False)

    def tearDown(self):
        self.idp.delete()
        super().tearDown()

    @classmethod
    def tearDownClass(cls):
        cls.account.delete()
        super().tearDownClass()


class TestAutoDeactivationTask(TestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.account = generator.get_billing_account_for_idp()
        cls.account.enterprise_admin_emails = ['test@vaultwax.com']
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

        cls.idp = generator.create_idp('vaultwax', cls.account)
        cls.idp.enable_user_deactivation = True
        cls.idp.idp_type = IdentityProviderType.ENTRA_ID
        cls.idp.save()
        cls.email_domain = AuthenticatedEmailDomain.objects.create(
            email_domain='vaultwax.com',
            identity_provider=cls.idp,
        )
        idp_patcher = patch('corehq.apps.sso.models.IdentityProvider.get_all_members_of_the_idp')
        cls.mock_get_all_members_of_the_idp = idp_patcher.start()
        cls.addClassCleanup(idp_patcher.stop)

    def setUp(self):
        super().setUp()
        self.web_user_a = self._create_web_user('a@vaultwax.com')
        self.web_user_b = self._create_web_user('b@vaultwax.com')
        self.web_user_c = self._create_web_user('c@vaultwax.com')
        # web_user_d is required so the total number of IdP user meet the threshold for auto-deactivation
        self.web_user_d = self._create_web_user('d@vaultwax.com')

    def test_user_is_deactivated_if_not_member_of_idp(self):
        self.assertTrue(self.web_user_c.is_active)
        self.mock_get_all_members_of_the_idp.return_value = [self.web_user_a.username, self.web_user_b.username]

        auto_deactivate_removed_sso_users()

        # Refetch Web User
        web_user = WebUser.get_by_username(self.web_user_c.username)
        self.assertFalse(web_user.is_active)

    def test_sso_exempt_users_are_not_deactivated(self):
        sso_exempt = self._create_web_user('exempt@vaultwax.com')
        UserExemptFromSingleSignOn.objects.create(
            username=sso_exempt.username,
            email_domain=self.email_domain,
        )
        self.mock_get_all_members_of_the_idp.return_value = [self.web_user_a.username, self.web_user_b.username]

        auto_deactivate_removed_sso_users()

        # Refetch Web User
        web_user = WebUser.get_by_username(sso_exempt.username)
        self.assertTrue(web_user.is_active)

    @patch('corehq.apps.sso.tasks.send_html_email_async.delay')
    def test_deactivation_skipped_if_entra_return_empty_sso_user(self, mock_send):
        self.mock_get_all_members_of_the_idp.return_value = []

        auto_deactivate_removed_sso_users()

        # Refetch Web User
        web_user_a = WebUser.get_by_username(self.web_user_a.username)
        self.assertTrue(web_user_a.is_active)
        web_user_b = WebUser.get_by_username(self.web_user_b.username)
        self.assertTrue(web_user_b.is_active)
        web_user_c = WebUser.get_by_username(self.web_user_c.username)
        self.assertTrue(web_user_c.is_active)
        mock_send.assert_called_once()

    def test_deactivation_skip_members_of_the_domains_but_not_have_an_email_domain_controlled_by_the_IdP(self):
        dimagi_user = self._create_web_user('superuser@dimagi.com')
        self.mock_get_all_members_of_the_idp.return_value = [self.web_user_a.username, self.web_user_b.username]

        auto_deactivate_removed_sso_users()

        # Refetch Web User
        dimagi_user = WebUser.get_by_username(dimagi_user.username)
        self.assertTrue(dimagi_user.is_active)
        web_user_c = WebUser.get_by_username(self.web_user_c.username)
        self.assertFalse(web_user_c.is_active)

    def _create_web_user(self, username):
        user = WebUser.create(
            self.domain.name, username, 'testpwd', None, None
        )
        self.addCleanup(user.delete, self.domain.name, deleted_by=None)
        return user
