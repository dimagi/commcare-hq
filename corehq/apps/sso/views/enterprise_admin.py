from memoized import memoized

from django.contrib import messages
from django.core.exceptions import ObjectDoesNotExist
from django.http import Http404, HttpResponseRedirect
from django.urls import reverse
from django.utils.translation import gettext as _, gettext_lazy

from corehq.apps.enterprise.views import BaseEnterpriseAdminView
from corehq.apps.hqwebapp.async_handler import AsyncHandlerMixin
from corehq.apps.sso.async_handlers import SSOExemptUsersAdminAsyncHandler, SsoTestUserAdminAsyncHandler
from corehq.apps.sso.certificates import get_certificate_response
from corehq.apps.sso.forms import (
    SsoSamlEnterpriseSettingsForm,
    SsoOidcEnterpriseSettingsForm,
)
from corehq.apps.sso.models import IdentityProvider, IdentityProviderProtocol

from corehq.toggles import MULTI_VIEW_API_KEYS


class ManageSSOEnterpriseView(BaseEnterpriseAdminView):
    page_title = gettext_lazy("Manage Single Sign-On")
    urlname = 'manage_sso'
    template_name = 'sso/enterprise_admin/manage_sso.html'

    @property
    def page_context(self):
        return {
            'identity_providers': IdentityProvider.objects.filter(
                owner=self.request.account, is_editable=True
            ).all(),
            'account': self.request.account,
        }


class EditIdentityProviderEnterpriseView(BaseEnterpriseAdminView, AsyncHandlerMixin):
    page_title = gettext_lazy("Edit Identity Provider")
    urlname = 'edit_idp_enterprise'
    template_name = 'sso/enterprise_admin/edit_identity_provider.html'
    async_handlers = [
        SSOExemptUsersAdminAsyncHandler,
        SsoTestUserAdminAsyncHandler,
    ]

    @property
    def page_url(self):
        return reverse(self.urlname, args=(self.domain, self.idp_slug))

    @property
    @memoized
    def idp_slug(self):
        return self.kwargs['idp_slug']

    @property
    def parent_pages(self):
        return [
            {
                'title': ManageSSOEnterpriseView.page_title,
                'url': reverse('manage_sso', args=(self.domain,)),
            },
        ]

    @property
    def page_context(self):
        return {
            'edit_idp_form': self.edit_enterprise_idp_form,
            'idp_slug': self.idp_slug,
            'show_api_fields': self.show_api_fields(),
            'toggle_client_secret': (
                self.identity_provider.protocol == IdentityProviderProtocol.OIDC
                and self.identity_provider.client_secret
            ),
        }

    @property
    @memoized
    def identity_provider(self):
        try:
            return IdentityProvider.objects.get(
                slug=self.idp_slug, owner=self.request.account, is_editable=True
            )
        except ObjectDoesNotExist:
            raise Http404()

    def get(self, request, *args, **kwargs):
        if 'sp_cert_public' in request.GET:
            return get_certificate_response(
                self.identity_provider.sp_cert_public,
                f"{self.identity_provider.slug}_sp_public.cer"
            )
        if 'idp_cert_public' in request.GET:
            return get_certificate_response(
                self.identity_provider.idp_cert_public,
                f"{self.identity_provider.slug}_idp_public.cer"
            )
        if 'sp_rollover_cert_public' in request.GET:
            return get_certificate_response(
                self.identity_provider.sp_rollover_cert_public,
                f"{self.identity_provider.slug}_sp_rollover_public.cer"
            )
        return super().get(request, args, kwargs)

    @property
    @memoized
    def edit_enterprise_idp_form(self):
        form_class = (
            SsoSamlEnterpriseSettingsForm if self.identity_provider.protocol == IdentityProviderProtocol.SAML
            else SsoOidcEnterpriseSettingsForm
        )

        uses_api_key_management = MULTI_VIEW_API_KEYS.enabled_for_request(self.request)

        if self.request.method == 'POST':
            return form_class(
                self.identity_provider,
                self.request.POST,
                self.request.FILES,
                uses_api_key_management=uses_api_key_management
            )

        return form_class(self.identity_provider, uses_api_key_management=uses_api_key_management)

    def post(self, request, *args, **kwargs):
        if self.async_response is not None:
            return self.async_response
        if self.edit_enterprise_idp_form.is_valid():
            self.edit_enterprise_idp_form.update_identity_provider(self.request.user)
            messages.success(request, _("Identity Provider updated!"))
            # we redirect here to force the memoized identity_provider property
            # to re-fetch its data.
            return HttpResponseRedirect(self.page_url)
        else:
            messages.error(
                request,
                _("Please check form for errors.")
            )
        return self.get(request, *args, **kwargs)
