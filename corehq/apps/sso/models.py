from django.db import models
from django.contrib.postgres.fields import ArrayField

from corehq.apps.accounting.models import BillingAccount


class IdentityProviderType(object):
    AZURE_AD = 'azure_ad'
    CHOICES = (
        (AZURE_AD, "Azure AD"),
    )


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
