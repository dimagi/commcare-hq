import datetime
from unittest.mock import ANY, patch

from django.test import TestCase
from freezegun import freeze_time

from corehq.apps.sso.certificates import DEFAULT_EXPIRATION
from corehq.apps.sso.tasks import (
    IDP_CERT_EXPIRES_REMINDER_DAYS,
    idp_cert_expires_reminder,
    renew_service_provider_x509_certificates,
    create_rollover_service_provider_x509_certificates,
    send_api_token_expiration_reminder,
)
from corehq.apps.sso.tests import generator


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
