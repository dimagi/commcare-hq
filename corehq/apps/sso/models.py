from django.db import models
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.urls import reverse
from django.utils.translation import gettext_lazy

from corehq.apps.accounting.models import BillingAccount, Subscription
from corehq.apps.sso import certificates
from corehq.apps.sso.exceptions import ServiceProviderCertificateError
from corehq.apps.sso.utils.user_helpers import get_email_domain_from_username
from corehq.util.quickcache import quickcache


class IdentityProviderType:
    AZURE_AD = 'azure_ad'
    ONE_LOGIN = 'one_login'
    OKTA = 'okta'
    CHOICES = (
        (AZURE_AD, "Entra ID"),
        (ONE_LOGIN, "One Login"),
        (OKTA, "Okta"),
    )


class IdentityProviderProtocol:
    SAML = 'saml'
    OIDC = 'oidc'
    CHOICES = (
        (SAML, "SAML 2.0"),
        (OIDC, "OpenID Connect (OIDC)"),
    )

    @classmethod
    def get_supported_types(cls):
        return {
            cls.SAML: (
                (IdentityProviderType.AZURE_AD, "Entra ID"),
            ),
            cls.OIDC: (
                (IdentityProviderType.ONE_LOGIN, "One Login"),
                (IdentityProviderType.OKTA, "Okta"),
            )
        }


class LoginEnforcementType:
    GLOBAL = 'global'
    TEST = 'test'
    CHOICES = (
        (GLOBAL, "Global"),
        (TEST, "Test"),
    )


class ServiceProviderCertificate:

    def __init__(self):
        """
        To increase the security with SAML transactions, we will provide the IdP
        with our public key for an x509 certificate unique to our interactions with
        a particular IdP. This certificate will be regenerated automatically by
        a periodic task every year.
        """
        key_pair = certificates.create_key_pair()
        cert = certificates.create_self_signed_cert(key_pair)

        self.public_key = certificates.get_public_key(cert)
        self.private_key = certificates.get_private_key(key_pair)
        self.date_expires = certificates.get_expiration_date(cert)


VALID_API_EXPIRATION_OPTIONS = [
    (365, gettext_lazy('1 Year')),
    (180, gettext_lazy('180 Days')),
    (120, gettext_lazy('120 Days')),
    (60, gettext_lazy('60 Days')),
    (30, gettext_lazy('30 Days'))
]


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
        max_length=50,
        default=IdentityProviderType.AZURE_AD,
        choices=IdentityProviderType.CHOICES,
    )
    protocol = models.CharField(
        max_length=5,
        default=IdentityProviderProtocol.SAML,
        choices=IdentityProviderProtocol.CHOICES,
    )

    # whether an IdP is editable by its BillingAccount owner
    # (it will always be editable by accounting admins)
    is_editable = models.BooleanField(default=False)

    # whether an IdP is actively in use as an authentication method on HQ
    is_active = models.BooleanField(default=False)

    # determines how the is_active behavior enforces the login policy on the homepage
    login_enforcement_type = models.CharField(
        max_length=10,
        default=LoginEnforcementType.GLOBAL,
        choices=LoginEnforcementType.CHOICES,
    )

    # the enterprise admins of this account will be able to edit the SAML
    # configuration fields
    owner = models.ForeignKey(BillingAccount, on_delete=models.PROTECT)

    entity_id = models.TextField(blank=True, null=True)

    # these are fields required by the external IdP to form a SAML request
    login_url = models.TextField(blank=True, null=True)
    logout_url = models.TextField(blank=True, null=True)
    idp_cert_public = models.TextField(blank=True, null=True)

    # needed for OIDC
    client_id = models.TextField(blank=True, null=True)
    client_secret = models.TextField(blank=True, null=True)

    # the date the IdP's SAML signing certificate expires.
    # this will be filled out by enterprise admins
    date_idp_cert_expiration = models.DateTimeField(blank=True, null=True)

    # Requires that <saml:Assertion> elements received by the SP are encrypted.
    # In Azure AD this requires that Token Encryption is enabled, a premium feature
    require_encrypted_assertions = models.BooleanField(default=False)

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

    # for auto-deactivation web user purposes
    enable_user_deactivation = models.BooleanField(default=False)
    api_host = models.TextField(default="")  # tenant id
    api_id = models.TextField(default="")  # application (client) id in Azure AD
    api_secret = models.TextField(default="")
    date_api_secret_expiration = models.DateField(blank=True, null=True)

    always_show_user_api_keys = models.BooleanField(default=False)
    max_days_until_user_api_key_expiration = models.IntegerField(
        default=None, null=True, blank=True, choices=VALID_API_EXPIRATION_OPTIONS
    )

    class Meta:
        app_label = 'sso'

    def __str__(self):
        return f"{self.name} IdP [{self.idp_type}]"

    @property
    def service_name(self):
        return dict(IdentityProviderType.CHOICES)[self.idp_type]

    def create_service_provider_certificate(self):
        sp_cert = ServiceProviderCertificate()
        self.sp_cert_public = sp_cert.public_key
        self.sp_cert_private = sp_cert.private_key
        self.date_sp_cert_expiration = sp_cert.date_expires
        self.save()

    def create_rollover_service_provider_certificate(self):
        sp_cert = ServiceProviderCertificate()
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

    def get_email_domains(self):
        return AuthenticatedEmailDomain.objects.filter(
            identity_provider=self
        ).values_list('email_domain', flat=True).all()

    def get_sso_exempt_users(self):
        return UserExemptFromSingleSignOn.objects.filter(
            email_domain__identity_provider=self,
        ).values_list('username', flat=True)

    def get_login_url(self, username=None):
        """
        Gets the login endpoint for the IdentityProvider based on the protocol
        being used.
        :param username: (string) username to pre-populate IdP login with
        :return: (String) identity provider login url
        """
        login_view_name = 'sso_saml_login' if self.protocol == IdentityProviderProtocol.SAML else 'sso_oidc_login'
        return '{}?username={}'.format(
            reverse(login_view_name, args=(self.slug,)),
            username
        )

    def get_active_projects(self):
        """
        Returns a list of active domains/project spaces for this identity
        provider.
        :return: list of strings (domain names)
        """
        return list(Subscription.visible_objects.filter(
            account=self.owner,
            is_active=True
        ).values_list('subscriber__domain', flat=True))

    @quickcache(['self.slug', 'domain'])
    def is_domain_an_active_member(self, domain):
        """
        Checks whether the given Domain is an Active Member of the current
        Identity Provider.

        An "Active Member" is defined by having an active Subscription that
        belongs to the BillingAccount owner of this IdentityProvider.

        :param domain: String (the Domain name)
        :return: Boolean (True if Domain is an Active Member)
        """
        return Subscription.visible_objects.filter(
            account=self.owner,
            is_active=True,
            subscriber__domain=domain,
        ).exists()

    @quickcache(['self.slug', 'domain'])
    def does_domain_trust_this_idp(self, domain):
        """
        Checks whether the given Domain trusts this Identity Provider.
        :param domain: String (the Domain name)
        :return: Boolean (True if Domain trusts this Identity Provider)
        """
        is_active_member = self.is_domain_an_active_member(domain)
        if not is_active_member:
            # Since this Domain is not an Active Member, check whether an
            # administrator of this domain has trusted this Identity Provider
            return TrustedIdentityProvider.objects.filter(
                domain=domain, identity_provider=self
            ).exists()
        return is_active_member

    def clear_domain_caches(self, domain):
        """
        Clear all caches associated with a Domain and this IdentityProvider
        :param domain: String (the Domain name)
        """
        IdentityProvider.does_domain_trust_this_idp.clear(self, domain)
        IdentityProvider.is_domain_an_active_member.clear(self, domain)
        from corehq.apps.sso.utils.domain_helpers import is_domain_using_sso
        is_domain_using_sso.clear(domain)

    @staticmethod
    def clear_email_domain_caches(email_domain):
        """
        Clears all caches associated with a given email_domain
        :param email_domain: String (email domain)
        """
        IdentityProvider.get_active_identity_provider_by_email_domain.clear(
            IdentityProvider,
            email_domain
        )

    def clear_all_email_domain_caches(self):
        """
        Clears the email_domain-related caches of all the email domains
        associated with this IdentityProvider.
        """
        all_email_domains_for_idp = AuthenticatedEmailDomain.objects.filter(
            identity_provider=self).values_list('email_domain', flat=True)
        for email_domain in all_email_domains_for_idp:
            self.clear_email_domain_caches(email_domain)

    def clear_all_domain_subscriber_caches(self):
        """
        Ensure that we clear all domain caches tied to the Subscriptions
        associated with the BillingAccount owner of this IdentityProvider.
        """
        for domain in self.get_active_projects():
            self.clear_domain_caches(domain)

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        self.clear_all_email_domain_caches()
        self.clear_all_domain_subscriber_caches()

    def create_trust_with_domain(self, domain, username):
        """
        This creates a TrustedIdentityProvider relationship between the Domain
        and the current Identity Provider.
        :param domain: String (the Domain name)
        :param username: String (the username of the user creating this agreement)
        :return: Boolean (True if a new trust was created, False if it already exists)
        """
        if not TrustedIdentityProvider.objects.filter(
            domain=domain, identity_provider=self
        ).exists():
            TrustedIdentityProvider.objects.create(
                domain=domain,
                identity_provider=self,
                acknowledged_by=username,
            )
            return True
        return False

    @classmethod
    def domain_has_editable_identity_provider(cls, domain):
        """
        Check to see that a Domain is associated with an IdentityProvider
        that is editable.
        :param domain: (String) Domain name
        :return: Boolean (True if an editable IdentityProvider exists)
        """
        owner = BillingAccount.get_account_by_domain(domain)
        return cls.objects.filter(owner=owner, is_editable=True).exists()

    @classmethod
    @quickcache(['cls.__name__', 'email_domain'])
    def get_active_identity_provider_by_email_domain(cls, email_domain):
        """
        Returns the active Identity Provider associated with a given email
        domain or None.
        :param email_domain: (string)
        :return: IdentityProvider or None
        """
        try:
            authenticated_email_domain = AuthenticatedEmailDomain.objects.get(
                email_domain=email_domain
            )
            idp = authenticated_email_domain.identity_provider
        except AuthenticatedEmailDomain.DoesNotExist:
            return None
        return idp if idp.is_active else None

    @classmethod
    def get_active_identity_provider_by_username(cls, username):
        """
        Returns the active Identity Provider associated with a user's email
        domain or None.
        :param username: (string)
        :return: IdentityProvider or None
        """
        email_domain = get_email_domain_from_username(username)
        if not email_domain:
            # malformed username/email
            return None
        return cls.get_active_identity_provider_by_email_domain(email_domain)

    @classmethod
    def does_domain_trust_user(cls, domain, username):
        """
        Check to see if the given domain trusts the user's IdentityProvider
        (if applicable) based on their email domain. If the user has no
        IdentityProvider, it will also return True.
        :param domain: (String) name of the domain
        :param username: (String) username of the user
        :return: Boolean (True if an IdP trust exists or is not applicable)
        """
        idp = cls.get_active_identity_provider_by_username(username)
        if idp is None:
            return True
        return idp.does_domain_trust_this_idp(domain)

    @classmethod
    def get_required_identity_provider(cls, username):
        """
        Gets the Identity Provider for the given username only if that
        user is required to login or sign up with that Identity Provider.

        An Identity Provider is required if:
        - it exists
        - is active
        - is Globally enforcing logins (login_enforcement_type) or is in Test login_enforcement_type
          and there is an SsoTestUser that maps to the given username

        :param username: String
        :return: IdentityProvider or None
        """
        idp = cls.get_active_identity_provider_by_username(username)
        if not idp:
            return None
        if (idp.login_enforcement_type == LoginEnforcementType.GLOBAL
                and not UserExemptFromSingleSignOn.objects.filter(username=username).exists()):
            return idp
        if (idp.login_enforcement_type == LoginEnforcementType.TEST
                and SsoTestUser.objects.filter(username=username).exists()):
            return idp
        return None


@receiver(post_save, sender=Subscription)
@receiver(post_delete, sender=Subscription)
def clear_caches_when_subscription_status_changes(sender, instance, **kwargs):
    """
    Catches the post-save and post-delete signals of Subscription to ensure
    that if the Subscription status for a domain changes, that the
    domain-related caches for IdentityProvider are all cleared.
    :param sender: The sender class (in this case Subscription)
    :param instance: Subscription - the instance being saved/deleted
    :param kwargs:
    """
    for identity_provider in IdentityProvider.objects.filter(owner=instance.account):
        identity_provider.clear_domain_caches(instance.subscriber.domain)


class AuthenticatedEmailDomain(models.Model):
    """
    This specifies the email domains that are tied to an Identity Provider and
    a list of users that would be exempt from SSO.
    """
    email_domain = models.CharField(max_length=256, db_index=True, unique=True)
    identity_provider = models.ForeignKey(IdentityProvider, on_delete=models.PROTECT)

    class Meta:
        app_label = 'sso'

    def __str__(self):
        return f"{self.email_domain} authenticated by [{self.identity_provider.name}]"


@receiver(post_save, sender=AuthenticatedEmailDomain)
@receiver(post_delete, sender=AuthenticatedEmailDomain)
def clear_caches_for_email_domain(sender, instance, **kwargs):
    """
    Catches the post-save and post-delete signals of AuthenticatedEmailDomain
    to ensure that we immediately clear the related email-domain quickcaches
    for IdentityProvider.
    :param sender: The sender class (in this case AuthenticatedEmailDomain)
    :param instance: AuthenticatedEmailDomain - the instance being saved/deleted
    :param kwargs:
    """
    IdentityProvider.clear_email_domain_caches(instance.email_domain)


class UserExemptFromSingleSignOn(models.Model):
    """
    This specifies what users are exempt from SSO for a given
    AuthenticatedEmailDomain. Other users will be required to use SSO once
    an AuthenticatedEmailDomain is specified for their email domain.
    """
    username = models.CharField(max_length=128, db_index=True)
    email_domain = models.ForeignKey(AuthenticatedEmailDomain, on_delete=models.CASCADE)

    class Meta:
        app_label = 'sso'

    def __str__(self):
        return f"{self.username} is exempt from SSO with {self.email_domain}"


class SsoTestUser(models.Model):
    """
    This specifies users who are able to log in with SSO from the homepage when testing mode is turned on
    for their Identity Provider.
    """
    username = models.CharField(max_length=128, db_index=True)
    email_domain = models.ForeignKey(AuthenticatedEmailDomain, on_delete=models.CASCADE)

    class Meta:
        app_label = 'sso'

    def __str__(self):
        return f"{self.username} is testing SSO with {self.email_domain}"


class TrustedIdentityProvider(models.Model):
    """
    This specifies the trust between domains (who are not associated with the
    IdP's BillingAccount owner) and an IdentityProvider
    """
    domain = models.CharField(max_length=256, db_index=True)
    identity_provider = models.ForeignKey(IdentityProvider, on_delete=models.PROTECT)
    date_acknowledged = models.DateTimeField(auto_now_add=True)
    acknowledged_by = models.EmailField()

    class Meta:
        app_label = 'sso'

    def __str__(self):
        return f"{self.domain} trusts [{self.identity_provider.name}]"


@receiver(post_save, sender=TrustedIdentityProvider)
@receiver(post_delete, sender=TrustedIdentityProvider)
def clear_caches_when_trust_is_established_or_removed(sender, instance, **kwargs):
    """
    Catches the post-save and post-delete signals of TrustedIdentityProvider
    to ensure that we immediately clear the related domain quickcaches
    for IdentityProvider.
    :param sender: The sender class (in this case AuthenticatedEmailDomain)
    :param instance: TrustedIdentityProvider - the instance being saved/deleted
    :param kwargs:
    """
    instance.identity_provider.clear_domain_caches(instance.domain)
