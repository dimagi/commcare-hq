from memoized import memoized

from corehq.apps.accounting.async_handlers import BaseSelect2AsyncHandler
from corehq.apps.accounting.models import BillingAccount
from corehq.apps.hqwebapp.async_handler import (
    BaseAsyncHandler,
    AsyncHandlerError,
)
from corehq.apps.sso.models import (
    AuthenticatedEmailDomain,
    IdentityProvider,
    UserExemptFromSingleSignOn,
)
from corehq.apps.sso.utils.user_helpers import get_email_domain_from_username


class Select2IdentityProviderHandler(BaseSelect2AsyncHandler):
    slug = 'select2_identity_provider'
    allowed_actions = [
        'owner',
    ]

    @property
    def owner_response(self):
        accounts = BillingAccount.objects.filter(is_customer_billing_account=True)
        if self.search_string:
            accounts = accounts.filter(name__icontains=self.search_string)
        return [(a.id, a.name) for a in accounts.order_by('name')]


class BaseLinkedObjectAsyncHandler(BaseAsyncHandler):
    allowed_actions = [
        'get_linked_objects',
        'add_object',
        'remove_object',
    ]

    def get_linked_objects(self):
        raise NotImplementedError("please implement get_linked_objects")

    def add_object(self):
        raise NotImplementedError("please implement add_object")

    def remove_object(self):
        raise NotImplementedError("please implement add_object")

    @property
    def get_linked_objects_response(self):
        return {
            'linkedObjects': self.get_linked_objects(),
        }

    @property
    def add_object_response(self):
        self.add_object()
        return {
            'linkedObjects': self.get_linked_objects(),
        }

    @property
    def remove_object_response(self):
        self.remove_object()
        return {
            'linkedObjects': self.get_linked_objects(),
        }


class IdentityProviderAdminAsyncHandler(BaseLinkedObjectAsyncHandler):
    slug = 'identity_provider_admin'

    def get_linked_objects(self):
        return list(AuthenticatedEmailDomain.objects.filter(
            identity_provider__slug=self.idp_slug
        ).order_by('email_domain').values_list('email_domain', flat=True))

    def add_object(self):
        if AuthenticatedEmailDomain.objects.filter(email_domain=self.email_domain).exists():
            raise AsyncHandlerError(
                f"Email domain {self.email_domain} is already associated"
                f"with an identity provider."
            )
        AuthenticatedEmailDomain.objects.create(
            identity_provider=self.identity_provider,
            email_domain=self.email_domain,
        )

    def remove_object(self):
        existing_email_domain = AuthenticatedEmailDomain.objects.filter(
            email_domain=self.email_domain,
            identity_provider=self.identity_provider,
        )
        if not existing_email_domain.exists():
            raise AsyncHandlerError(
                f"No email domain exists with the name {self.email_domain}."
            )
        existing_email_domain.delete()

    @property
    @memoized
    def idp_slug(self):
        return self.data.get('requestContext[idpSlug]')

    @property
    @memoized
    def identity_provider(self):
        return IdentityProvider.objects.get(slug=self.idp_slug)

    @property
    @memoized
    def email_domain(self):
        return self.data.get('objectName')


class SSOExemptUsersAdminAsyncHandler(BaseLinkedObjectAsyncHandler):
    slug = 'sso_exempt_users_admin'

    def get_linked_objects(self):
        return list(UserExemptFromSingleSignOn.objects.filter(
            email_domain__identity_provider__slug=self.idp_slug
        ).order_by('username').values_list('username', flat=True))

    def add_object(self):
        if UserExemptFromSingleSignOn.objects.filter(username=self.username).exists():
            raise AsyncHandlerError(
                f"User {self.username} is already exempt from SSO",
            )
        auth_email_domain = AuthenticatedEmailDomain.objects.filter(
            identity_provider__slug=self.idp_slug,
            email_domain=self.email_domain
        )
        if not auth_email_domain.exists():
            raise AsyncHandlerError(
                f"Please ensure that '{self.email_domain}' is added as an "
                f"Authenticated Email Domain for this Identity Provider "
                f"before proceeding."
            )
        UserExemptFromSingleSignOn.objects.create(
            username=self.username,
            email_domain=auth_email_domain.first(),
        )

    def remove_object(self):
        if len(self.get_linked_objects()) == 1 and self.identity_provider.is_editable:
            raise AsyncHandlerError(
                "At least one admin must be exempt from SSO in case of "
                "failure connecting with an Identity Provider."
            )
        existing_exempt_user = UserExemptFromSingleSignOn.objects.filter(
            username=self.username,
            email_domain__identity_provider__slug=self.idp_slug
        )
        if not existing_exempt_user.exists():
            raise AsyncHandlerError(
                f"The user {self.username} was never exempt from SSO with "
                f"this Identity Provider and the {self.email_domain} "
                f"Email Domain."
            )
        existing_exempt_user.delete()

    @property
    @memoized
    def idp_slug(self):
        return self.data.get('requestContext[idpSlug]')

    @property
    @memoized
    def identity_provider(self):
        return IdentityProvider.objects.get(slug=self.idp_slug)

    @property
    @memoized
    def username(self):
        return self.data.get('objectName')

    @property
    @memoized
    def email_domain(self):
        email_domain = get_email_domain_from_username(self.username)
        if not email_domain:
            raise AsyncHandlerError("Please enter in a valid email.")
        return email_domain
