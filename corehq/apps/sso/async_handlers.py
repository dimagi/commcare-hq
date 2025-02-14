from gettext import gettext

from django.http import Http404
from memoized import memoized

from corehq.apps.accounting.async_handlers import BaseSelect2AsyncHandler
from corehq.apps.accounting.models import BillingAccount, SoftwarePlanEdition, Subscription
from corehq.apps.hqwebapp.async_handler import (
    BaseAsyncHandler,
    AsyncHandlerError,
)
from corehq.apps.sso.models import (
    AuthenticatedEmailDomain,
    IdentityProvider,
    UserExemptFromSingleSignOn,
    SsoTestUser,
)
from corehq.apps.sso.utils.user_helpers import get_email_domain_from_username


class Select2IdentityProviderHandler(BaseSelect2AsyncHandler):
    slug = 'select2_identity_provider'
    allowed_actions = [
        'owner',
    ]

    @property
    def owner_response(self):
        advanced_subscriptions = Subscription.objects.filter(
            plan_version__plan__edition=SoftwarePlanEdition.ADVANCED,
            is_active=True,
        )
        advanced_accounts = BillingAccount.objects.filter(
            id__in=advanced_subscriptions.values_list('account', flat=True),
            is_active=True,
        )
        customer_billing_accounts = BillingAccount.objects.filter(
            is_customer_billing_account=True,
            is_active=True,
        )
        accounts = advanced_accounts | customer_billing_accounts
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
    def idp_slug(self):
        return self.data.get('requestContext[idpSlug]')

    @property
    @memoized
    def identity_provider(self):
        return IdentityProvider.objects.get(slug=self.idp_slug)

    def check_that_idp_matches_request_account_or_404(self):
        if self.request.user.is_superuser:
            return
        if not self.identity_provider.owner == self.request.account:
            raise Http404()

    @property
    def get_linked_objects_response(self):
        self.check_that_idp_matches_request_account_or_404()
        return {
            'linkedObjects': self.get_linked_objects(),
        }

    @property
    def add_object_response(self):
        self.check_that_idp_matches_request_account_or_404()
        self.add_object()
        return {
            'linkedObjects': self.get_linked_objects(),
        }

    @property
    def remove_object_response(self):
        self.check_that_idp_matches_request_account_or_404()
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
                gettext(
                    "Email domain '{}' is already associated with an identity provider."
                ).format(self.email_domain)
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
                gettext("No email domain exists with the name {}.").format(self.email_domain)
            )
        existing_email_domain.delete()

    @property
    @memoized
    def email_domain(self):
        return self.data.get('objectName')


class BaseSsoUsersAdminAsyncHandler(BaseLinkedObjectAsyncHandler):

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

    def _get_authenticated_email_domain(self):
        auth_email_domain = AuthenticatedEmailDomain.objects.filter(
            identity_provider__slug=self.idp_slug,
            email_domain=self.email_domain
        )
        if not auth_email_domain.exists():
            raise AsyncHandlerError(
                gettext(
                    "Please ensure that '{}' is added as an Authenticated Email Domain for this "
                    "Identity Provider before proceeding."
                ).format(self.email_domain)
            )
        return auth_email_domain


class SSOExemptUsersAdminAsyncHandler(BaseSsoUsersAdminAsyncHandler):
    slug = 'sso_exempt_users_admin'

    def get_linked_objects(self):
        return list(UserExemptFromSingleSignOn.objects.filter(
            email_domain__identity_provider__slug=self.idp_slug
        ).order_by('username').values_list('username', flat=True))

    def add_object(self):
        if UserExemptFromSingleSignOn.objects.filter(username=self.username).exists():
            raise AsyncHandlerError(
                gettext("User {} is already exempt from SSO").format(self.username),
            )
        auth_email_domain = self._get_authenticated_email_domain()
        test_user = SsoTestUser.objects.filter(
            username=self.username,
        )
        if test_user.exists():
            raise AsyncHandlerError(
                gettext(
                    "There is already a testing user {}. A user cannot both be a testing user and "
                    "exempt from SSO."
                ).format(self.username)
            )
        UserExemptFromSingleSignOn.objects.create(
            username=self.username,
            email_domain=auth_email_domain.first(),
        )

    def remove_object(self):
        if len(self.get_linked_objects()) == 1 and self.identity_provider.is_editable:
            raise AsyncHandlerError(
                gettext(
                    "At least one admin must be exempt from SSO in case of "
                    "failure connecting with an Identity Provider."
                )
            )
        existing_exempt_user = UserExemptFromSingleSignOn.objects.filter(
            username=self.username,
            email_domain__identity_provider__slug=self.idp_slug
        )
        if not existing_exempt_user.exists():
            raise AsyncHandlerError(
                gettext(
                    "The user {} was never exempt from SSO with this Identity Provider and the {} Email Domain."
                ).format(self.username, self.email_domain)
            )
        existing_exempt_user.delete()


class SsoTestUserAdminAsyncHandler(BaseSsoUsersAdminAsyncHandler):
    slug = 'sso_test_users_admin'

    def get_linked_objects(self):
        return list(SsoTestUser.objects.filter(
            email_domain__identity_provider__slug=self.idp_slug
        ).order_by('username').values_list('username', flat=True))

    def add_object(self):
        if SsoTestUser.objects.filter(username=self.username).exists():
            raise AsyncHandlerError(
                gettext("User {} is already a test user.").format(self.username),
            )
        auth_email_domain = self._get_authenticated_email_domain()
        exempt_user = UserExemptFromSingleSignOn.objects.filter(
            username=self.username,
        )
        if exempt_user.exists():
            raise AsyncHandlerError(
                gettext(
                    "There is already a user exempt from SSO with the username '{}'. "
                    "A user cannot both be a test user and exempt from SSO."
                ).format(self.username)
            )
        SsoTestUser.objects.create(
            username=self.username,
            email_domain=auth_email_domain.first(),
        )

    def remove_object(self):
        existing_test_user = SsoTestUser.objects.filter(
            username=self.username,
            email_domain__identity_provider__slug=self.idp_slug
        )
        if not existing_test_user.exists():
            raise AsyncHandlerError(
                gettext(
                    "The user {} was never a test user for this Identity Provider and the {} Email Domain."
                ).format(self.username, self.email_domain)
            )
        existing_test_user.delete()
