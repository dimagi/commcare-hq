from memoized import memoized

from django.contrib import messages
from django.core.exceptions import ObjectDoesNotExist
from django.http import Http404, HttpResponseRedirect
from django.urls import reverse
from django.utils.translation import ugettext as _, ugettext_lazy

from corehq.apps.enterprise.views import BaseEnterpriseAdminView
from corehq.apps.hqwebapp.async_handler import AsyncHandlerMixin
from corehq.apps.sso.async_handlers import SSOExemptUsersAdminAsyncHandler
from corehq.apps.sso.certificates import get_certificate_response
from corehq.apps.sso.forms import SSOEnterpriseSettingsForm
from corehq.apps.sso.models import IdentityProvider


class ManageSSOEnterpriseView(BaseEnterpriseAdminView):
    page_title = ugettext_lazy("Manage Single Sign-On")
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
    page_title = ugettext_lazy("Edit Identity Provider")
    urlname = 'edit_idp_enterprise'
    template_name = 'sso/enterprise_admin/edit_identity_provider.html'
    async_handlers = [
        SSOExemptUsersAdminAsyncHandler,
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
        if self.request.method == 'POST':
            return SSOEnterpriseSettingsForm(
                self.identity_provider, self.request.POST, self.request.FILES
            )
        return SSOEnterpriseSettingsForm(self.identity_provider)

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
