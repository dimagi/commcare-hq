from OpenSSL import crypto
import uuid
from dateutil.parser import parse

from django.conf import settings
from django.db import models
from django.contrib.postgres.fields import ArrayField

from corehq.apps.accounting.models import BillingAccount
from corehq.apps.sso.exceptions import ServiceProviderCertificateError


class IdentityProviderType(object):
    AZURE_AD = 'azure_ad'
    CHOICES = (
        (AZURE_AD, "Azure AD"),
    )


class ServiceProviderCertificate(object):
    DEFAULT_EXPIRATION = 365 * 24 * 60 * 60  # one year in seconds

    def __init__(self, identity_provider):
        """
        To increase the security with SAML transactions, we will provide the IdP
        with our public key for an x509 certificate unique to our interactions with
        a particular IdP. This certificate will be regenerated automatically by
        a periodic task every 60 days.
        """
        # create a key pair
        k = crypto.PKey()
        k.generate_key(crypto.TYPE_RSA, 4096)

        # create a self-signed cert
        cert = crypto.X509()
        cert.get_subject().C = "US"
        cert.get_subject().ST = "MA"
        cert.get_subject().L = "Cambridge"
        cert.get_subject().O = "Dimagi Inc."
        cert.get_subject().OU = "CommCareHQ"
        cert.get_subject().CN = "CommCare"
        cert.get_subject().emailAddress = settings.ACCOUNTS_EMAIL
        cert.set_serial_number(uuid.uuid4().int)
        cert.gmtime_adj_notBefore(0)
        cert.gmtime_adj_notAfter(self.DEFAULT_EXPIRATION)
        cert.set_issuer(cert.get_subject())
        cert.set_pubkey(k)
        cert.sign(k, "sha256")

        self.public_key = crypto.dump_certificate(crypto.FILETYPE_PEM, cert).decode("utf-8")
        self.private_key = crypto.dump_privatekey(crypto.FILETYPE_PEM, k).decode("utf-8")
        self.date_expires = parse(cert.get_notAfter())


class IdentityProvider(models.Model):
    """
    This stores the information necessary to make a SAML request to an external
    IdP. Right now this process supports Azure AD and the plan is to add
    support for other identity provider types in the future.
    """
    # these three fields must only ever be editable by Accounting admins
    name = models.CharField(max_length=128)
    slug = models.CharField(max_length=256, db_index=True, unique=True)
    idp_type = models.CharField(
        max_length=10,
        default=IdentityProviderType.AZURE_AD,
        choices=IdentityProviderType.CHOICES,
    )

    # whether an IdP is editable by its BillingAccount owner
    # (it will always be editable by accounting admins)
    is_editable = models.BooleanField(default=False)

    # whether an IdP is actively in use as an authentication method on HQ
    is_active = models.BooleanField(default=False)

    # the enterprise admins of this account will be able to edit the SAML
    # configuration fields
    owner = models.ForeignKey(BillingAccount, on_delete=models.PROTECT)

    # these are fields required by the external IdP to form a SAML request
    entity_id = models.TextField(blank=True, null=True)
    login_url = models.TextField(blank=True, null=True)
    logout_url = models.TextField(blank=True, null=True)
    idp_cert_public = models.TextField(blank=True, null=True)

    # the date the IdP's SAML signing certificate expires.
    # this will be filled out by enterprise admins
    date_idp_cert_expiration = models.DateTimeField(blank=True, null=True)

    # as the service provider, this will store our x509 certificates and
    # will be renewed automatically by a periodic task
    sp_cert_public = models.TextField(blank=True, null=True)
    sp_cert_private = models.TextField(blank=True, null=True)
    date_sp_cert_expiration = models.DateTimeField(blank=True, null=True)

    # as the x509 certificate expires, we need to provide the IdP with our next
    # "rollover" cert to prepare the IdP for the transfer
    sp_rollover_cert_public = models.TextField(blank=True, null=True)
    sp_rollover_cert_private = models.TextField(blank=True, null=True)
    date_sp_rollover_cert_expiration = models.DateTimeField(blank=True, null=True)

    # for auditing purposes
    created_on = models.DateTimeField(auto_now_add=True)
    created_by = models.EmailField()
    last_modified = models.DateTimeField(auto_now=True)
    last_modified_by = models.EmailField()

    class Meta(object):
        app_label = 'sso'

    def __str__(self):
        return f"{self.name} IdP [{self.idp_type}]"

    def create_service_provider_certificate(self):
        sp_cert = ServiceProviderCertificate(self)
        self.sp_cert_public = sp_cert.public_key
        self.sp_cert_private = sp_cert.private_key
        self.date_sp_cert_expiration = sp_cert.date_expires
        self.save()

    def create_rollover_service_provider_certificate(self):
        sp_cert = ServiceProviderCertificate(self)
        self.sp_rollover_cert_public = sp_cert.public_key
        self.sp_rollover_cert_private = sp_cert.private_key
        self.date_sp_rollover_cert_expiration = sp_cert.date_expires
        self.save()

    def renew_service_provider_certificate(self):
        if not self.sp_rollover_cert_public:
            raise ServiceProviderCertificateError(
                "A rollover certificate for the Service Provider was never "
                "generated. You should first create a rollover certificate and "
                "leave it active for a few days to give the IdP a heads up."
            )
        self.sp_cert_public = self.sp_rollover_cert_public
        self.sp_cert_private = self.sp_rollover_cert_private
        self.date_sp_cert_expiration = self.date_sp_rollover_cert_expiration
        self.sp_rollover_cert_public = None
        self.sp_rollover_cert_private = None
        self.date_sp_rollover_cert_expiration = None
        self.save()


class AuthenticatedEmailDomain(models.Model):
    """
    This specifies the email domains that are tied to an Identity Provider and
    a list of users that would be exempt from SSO.
    """
    email_domain = models.CharField(max_length=253, db_index=True, unique=True)
    identity_provider = models.ForeignKey(IdentityProvider, on_delete=models.PROTECT)
    sso_exempt_users = ArrayField(models.EmailField(), default=list, blank=True)

    class Meta(object):
        app_label = 'sso'

    def __str__(self):
        return f"{self.email_domain} authenticated by [{self.identity_provider.name}]"


class TrustedIdentityProvider(models.Model):
    """
    This specifies the trust between domains (who are not associated with the
    IdP's BillingAccount owner) and an IdentityProvider
    """
    domain = models.CharField(max_length=256, db_index=True)
    identity_provider = models.ForeignKey(IdentityProvider, on_delete=models.PROTECT)
    date_acknowledged = models.DateTimeField(auto_now_add=True)
    acknowledged_by = models.EmailField()

    class Meta(object):
        app_label = 'sso'

    def __str__(self):
        return f"{self.domain} trusts [{self.identity_provider.name}]"
