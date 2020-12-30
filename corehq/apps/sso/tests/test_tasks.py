import datetime

from corehq.apps.sso.models import (
    IdentityProvider,
    ServiceProviderCertificate,
)
from corehq.apps.sso.tasks import (
    renew_service_provider_x509_certificates,
    create_rollover_service_provider_x509_certificates,
)
from corehq.apps.sso.tests.base_tests import BaseSSOTest


def _get_days_before_expiration(days_before):
    return (ServiceProviderCertificate.DEFAULT_EXPIRATION / (24 * 60 * 60)) - days_before


class TestSSOTasks(BaseSSOTest):

    def setUp(self):
        super().setUp()
        self.idp = IdentityProvider(
            name=f"Azure AD for {self.account.name}",
            slug=f"{self.domain.name}-idp",
            owner=self.account
        )
        self.idp.save()

    def test_create_rollover_service_provider_x509_certificates(self):
        self.idp.create_service_provider_certificate()
        self.idp.date_sp_cert_expiration = (
            datetime.datetime.utcnow() -
            datetime.timedelta(days=_get_days_before_expiration(13))
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
            datetime.datetime.utcnow() -
            datetime.timedelta(seconds=_get_days_before_expiration(7))
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

    def tearDown(self):
        self.idp.delete()
        super().tearDown()
